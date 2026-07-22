from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class ExternalHttpRejected(ValueError):
    pass


def validate_restricted_https_url(url: str, allowed_hosts: set[str]) -> str:
    value = str(url or "").strip()
    if any(ord(character) < 32 for character in value) or "\\" in value:
        raise ExternalHttpRejected("URL contains forbidden characters.")
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ExternalHttpRejected("URL port is invalid.") from exc
    hostname = (parsed.hostname or "").casefold()
    if (
        parsed.scheme.casefold() != "https"
        or parsed.username is not None
        or parsed.password is not None
        or not hostname
        or hostname not in {host.casefold() for host in allowed_hosts}
        or port not in {None, 443}
    ):
        raise ExternalHttpRejected("HTTPS host is not approved.")
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
        }
    except OSError as exc:
        raise ExternalHttpRejected("Approved host could not be resolved.") from exc
    if not addresses:
        raise ExternalHttpRejected("Approved host has no addresses.")
    for address in addresses:
        try:
            parsed_address = ipaddress.ip_address(address)
        except ValueError as exc:
            raise ExternalHttpRejected("Resolved address is invalid.") from exc
        if not parsed_address.is_global:
            raise ExternalHttpRejected("Private or link-local destinations are forbidden.")
    return value


class _RestrictedRedirectHandler(HTTPRedirectHandler):
    def __init__(self, allowed_hosts: set[str]) -> None:
        super().__init__()
        self.allowed_hosts = allowed_hosts

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        checked_url = validate_restricted_https_url(
            urljoin(request.full_url, new_url),
            self.allowed_hosts,
        )
        return super().redirect_request(
            request,
            file_pointer,
            code,
            message,
            headers,
            checked_url,
        )


def fetch_restricted(
    request: Request,
    *,
    allowed_hosts: set[str],
    allowed_content_types: set[str],
    maximum_bytes: int,
    timeout_seconds: float,
) -> bytes:
    validate_restricted_https_url(request.full_url, allowed_hosts)
    opener = build_opener(_RestrictedRedirectHandler(allowed_hosts))
    with opener.open(request, timeout=timeout_seconds) as response:
        validate_restricted_https_url(response.geturl(), allowed_hosts)
        content_type = response.headers.get_content_type().casefold()
        if content_type not in {value.casefold() for value in allowed_content_types}:
            raise ExternalHttpRejected("Response content type is not approved.")
        raw_length = response.headers.get("Content-Length", "").strip()
        if raw_length:
            try:
                content_length = int(raw_length)
            except ValueError as exc:
                raise ExternalHttpRejected("Response content length is invalid.") from exc
            if content_length < 0 or content_length > maximum_bytes:
                raise ExternalHttpRejected("Response is too large.")
        payload = response.read(maximum_bytes + 1)
    if len(payload) > maximum_bytes:
        raise ExternalHttpRejected("Response is too large.")
    return payload
