from __future__ import annotations

import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from flask import Flask, Response, g, jsonify, request, session
from flask.logging import default_handler
from werkzeug.exceptions import RequestEntityTooLarge
from ogma.errors import ApplicationError


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CANONICAL_LOCAL_HOST = "oghma.local"
LOCAL_HOSTS = {CANONICAL_LOCAL_HOST}
MAX_REQUEST_BYTES = 256 * 1024 * 1024
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_JSON_DEPTH = 32
MAX_JSON_ITEMS = 10_000
MAX_MULTIPART_PARTS = 20


class LocalHostMiddleware:
    """Reject an untrusted Host header before Flask performs route dispatch."""

    def __init__(self, app: Callable, allowed_ports: set[int]) -> None:
        self.app = app
        self.allowed_ports = allowed_ports

    def __call__(self, environ, start_response):
        if not is_allowed_host(environ.get("HTTP_HOST", ""), self.allowed_ports):
            payload = b'{"error":{"code":"invalid_host","message":"Host is not allowed.","request_id":""}}'
            headers = [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(payload))),
                ("Cache-Control", "no-store"),
                ("X-Content-Type-Options", "nosniff"),
                ("X-Frame-Options", "DENY"),
            ]
            start_response("400 Bad Request", headers)
            return [payload]
        return self.app(environ, start_response)


def configure_local_security(app: Flask, data_dir: Path, expected_port: int) -> None:
    secret_path = Path(data_dir) / ".secrets" / "flask-secret-key"
    app.secret_key = load_or_create_install_secret(secret_path)
    app.config.update(
        MAX_CONTENT_LENGTH=MAX_REQUEST_BYTES,
        MAX_FORM_MEMORY_SIZE=MAX_JSON_BYTES,
        MAX_FORM_PARTS=MAX_MULTIPART_PARTS,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=False,
    )

    # The browser-facing origin is always http://oghma.local on port 80.
    # Waitress still binds internally to loopback:expected_port, but requests
    # addressed directly to that socket are rejected by Host validation.
    allowed_ports = {80}
    app.wsgi_app = LocalHostMiddleware(app.wsgi_app, allowed_ports)
    configure_structured_logging(app, data_dir)

    @app.before_request
    def enforce_request_boundary():
        g.request_id = secrets.token_hex(12)
        g.csp_nonce = secrets.token_urlsafe(18)
        g.request_started_at = time.monotonic()

        if request.method not in SAFE_METHODS:
            fetch_site = request.headers.get("Sec-Fetch-Site", "").strip().lower()
            if fetch_site == "cross-site":
                return security_error("cross_site_request", "Cross-site requests are not allowed.", 403)

            origin = request.headers.get("Origin", "").strip()
            referer = request.headers.get("Referer", "").strip()
            if origin:
                # Some desktop browser containers intentionally serialize the
                # origin as the opaque value `null` and omit Fetch Metadata.
                # The canonical Host boundary and mandatory CSRF token still
                # authenticate these requests; an explicit cross-site signal
                # is rejected above before this exception is considered.
                opaque_origin = origin.casefold() == "null"
                if not opaque_origin and not is_trusted_local_source(
                    origin,
                    request.host_url,
                    allowed_ports,
                ):
                    log_source_rejection(
                        app,
                        "invalid_origin",
                        origin,
                        fetch_site,
                    )
                    return security_error("invalid_origin", "Request origin is not allowed.", 403)
            elif referer:
                if not is_trusted_local_source(referer, request.host_url, allowed_ports):
                    log_source_rejection(
                        app,
                        "invalid_referer",
                        referer,
                        fetch_site,
                    )
                    return security_error("invalid_referer", "Request referer is not allowed.", 403)
            else:
                return security_error("missing_origin", "Browser origin information is required.", 403)

            expected_token = session.get("_csrf_token", "")
            supplied_token = request.headers.get("X-CSRF-Token", "").strip()
            if not supplied_token and not request.is_json:
                supplied_token = request.form.get("_csrf_token", "").strip()
            if (
                not expected_token
                or not supplied_token
                or not hmac.compare_digest(str(expected_token), supplied_token)
            ):
                return security_error("invalid_csrf", "CSRF token is missing or invalid.", 403)

        if request.is_json:
            content_length = request.content_length
            if content_length is not None and content_length > MAX_JSON_BYTES:
                return security_error("json_too_large", "JSON request is too large.", 413)
            raw = request.get_data(cache=True)
            if len(raw) > MAX_JSON_BYTES:
                return security_error("json_too_large", "JSON request is too large.", 413)
            if raw:
                try:
                    payload = json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return security_error("invalid_json", "JSON request is malformed.", 400)
                if not json_within_limits(payload):
                    return security_error(
                        "json_too_complex",
                        "JSON request exceeds nesting or item limits.",
                        422,
                    )
        return None

    @app.after_request
    def apply_security_headers(response: Response) -> Response:
        nonce = getattr(g, "csp_nonce", "")
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            "style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; "
            "img-src 'self' data: blob:; "
            "media-src 'self' blob:; "
            "object-src 'none'; "
            "base-uri 'none'; "
            "form-action 'self'; "
            "frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        app.logger.info(
            "request_complete",
            extra={
                "event": "request_complete",
                "request_id": getattr(g, "request_id", ""),
                "method": request.method,
                "route": request.url_rule.rule if request.url_rule else "unmatched",
                "status": response.status_code,
                "duration_ms": round(
                    (time.monotonic() - getattr(g, "request_started_at", time.monotonic()))
                    * 1000,
                    2,
                ),
            },
        )
        return response

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.errorhandler(ApplicationError)
    def handle_application_error(error: ApplicationError):
        return security_error(error.code, error.safe_message, error.status)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(_error: RequestEntityTooLarge):
        return security_error(
            "payload_too_large",
            "Submitted data is too large.",
            413,
        )

    @app.context_processor
    def security_template_context() -> dict[str, str]:
        return {"csp_nonce": getattr(g, "csp_nonce", "")}


def csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return str(token)


def load_or_create_install_secret(path: Path) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        descriptor = None
    if descriptor is not None:
        try:
            secret = secrets.token_bytes(48)
            os.write(descriptor, secret)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    secret = path.read_bytes()
    if len(secret) < 32:
        raise RuntimeError("The per-install Flask secret is missing or invalid.")
    return secret


def is_allowed_host(raw_host: str, allowed_ports: set[int]) -> bool:
    value = str(raw_host or "").strip().lower()
    if not value or any(character in value for character in ("\x00", "/", "\\", "@", "#", "?")):
        return False
    if value.count(":") > 1:
        return False
    if ":" in value:
        hostname, raw_port = value.rsplit(":", 1)
        if not raw_port.isdigit():
            return False
        port = int(raw_port)
        if port not in allowed_ports:
            return False
    else:
        hostname = value
    return hostname in LOCAL_HOSTS


def is_same_origin(candidate: str, current_host_url: str) -> bool:
    try:
        parsed = urlsplit(candidate)
        current = urlsplit(current_host_url)
        if parsed.scheme not in {"http", "https"}:
            return False
        if parsed.username is not None or parsed.password is not None:
            return False
        return (
            parsed.scheme.lower(),
            parsed.hostname.lower() if parsed.hostname else "",
            parsed.port or _default_port(parsed.scheme),
        ) == (
            current.scheme.lower(),
            current.hostname.lower() if current.hostname else "",
            current.port or _default_port(current.scheme),
        )
    except ValueError:
        return False


def is_trusted_local_source(
    candidate: str,
    current_host_url: str,
    allowed_ports: set[int],
) -> bool:
    """Treat approved loopback aliases and their configured ports as one local app."""
    if is_same_origin(candidate, current_host_url):
        return True
    try:
        parsed = urlsplit(candidate)
        current = urlsplit(current_host_url)
        if parsed.scheme.lower() != current.scheme.lower():
            return False
        if parsed.scheme.lower() != "http":
            return False
        if (
            parsed.username is not None
            or parsed.password is not None
            or current.username is not None
            or current.password is not None
        ):
            return False
        parsed_host = parsed.hostname.lower() if parsed.hostname else ""
        current_host = current.hostname.lower() if current.hostname else ""
        parsed_port = parsed.port or _default_port(parsed.scheme)
        current_port = current.port or _default_port(current.scheme)
        return (
            parsed_host in LOCAL_HOSTS
            and current_host in LOCAL_HOSTS
            and parsed_port in allowed_ports
            and current_port in allowed_ports
        )
    except ValueError:
        return False


def log_source_rejection(
    app: Flask,
    code: str,
    candidate: str,
    fetch_site: str,
) -> None:
    app.logger.warning(
        "security_boundary_rejected",
        extra={
            "event": "security_boundary_rejected",
            "request_id": getattr(g, "request_id", ""),
            "method": request.method,
            "route": request.path,
            "rejection_code": code,
            "request_host": request.host,
            "source_origin": safe_origin_label(candidate),
            "fetch_site": fetch_site or "missing",
        },
    )


def safe_origin_label(value: str) -> str:
    if str(value or "").strip().casefold() == "null":
        return "opaque"
    try:
        parsed = urlsplit(value)
        if not parsed.scheme or not parsed.hostname:
            return "invalid"
        port = parsed.port or _default_port(parsed.scheme)
        return f"{parsed.scheme.lower()}://{parsed.hostname.lower()}:{port}"
    except ValueError:
        return "invalid"


def json_within_limits(payload: Any) -> bool:
    item_count = 0
    stack = [(payload, 1)]
    while stack:
        value, depth = stack.pop()
        if depth > MAX_JSON_DEPTH:
            return False
        if isinstance(value, dict):
            item_count += len(value)
            if item_count > MAX_JSON_ITEMS:
                return False
            stack.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            item_count += len(value)
            if item_count > MAX_JSON_ITEMS:
                return False
            stack.extend((item, depth + 1) for item in value)
    return True


def security_error(code: str, message: str, status: int):
    return (
        jsonify(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": getattr(g, "request_id", ""),
                }
            }
        ),
        status,
    )


class _JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "event": getattr(record, "event", record.getMessage()),
            "request_id": getattr(record, "request_id", ""),
        }
        for field in (
            "method",
            "route",
            "status",
            "duration_ms",
            "operation_id",
            "rejection_code",
            "request_host",
            "source_origin",
            "fetch_site",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class _ClosingRotatingFileHandler(RotatingFileHandler):
    """Release the file after every record so Windows backup/test cleanup is not blocked."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            super().emit(record)
        finally:
            self.close()


def configure_structured_logging(app: Flask, data_dir: Path) -> None:
    if default_handler in app.logger.handlers:
        app.logger.removeHandler(default_handler)
    for existing in list(app.logger.handlers):
        if not getattr(existing, "_ogma_structured", False):
            continue
        app.logger.removeHandler(existing)
        existing.close()
    log_dir = Path(data_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = _ClosingRotatingFileHandler(
        log_dir / "ogma.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
        delay=True,
    )
    handler._ogma_structured = True  # type: ignore[attr-defined]
    handler.setFormatter(_JsonLogFormatter())
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def _default_port(scheme: str) -> int:
    return 443 if scheme.lower() == "https" else 80
