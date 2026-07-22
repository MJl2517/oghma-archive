from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request

from ogma.errors import ConflictError, ExternalOperationError
from ogma.external_http import ExternalHttpRejected, fetch_restricted
from ogma.json_store import JsonIntegrityError, read_json, write_json


GITHUB_OWNER = "MJl2517"
GITHUB_REPOSITORY = "oghma-archive"
GITHUB_API_VERSION = "2022-11-28"
LATEST_RELEASE_API = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPOSITORY}/releases/latest"
)
RELEASE_DOWNLOAD_PREFIX = (
    f"/{GITHUB_OWNER}/{GITHUB_REPOSITORY}/releases/download/"
)
API_HOSTS = {"api.github.com"}
DOWNLOAD_HOSTS = {
    "github.com",
    "release-assets.githubusercontent.com",
    "objects.githubusercontent.com",
}
MAX_RELEASE_JSON_BYTES = 2 * 1024 * 1024
MAX_CHECKSUM_BYTES = 16 * 1024
MAX_INSTALLER_BYTES = 256 * 1024 * 1024
CACHE_SECONDS = 5 * 60
VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def normalize_version(value: str) -> str:
    match = VERSION_PATTERN.fullmatch(str(value or "").strip())
    if not match:
        raise ValueError("Release tag is not a supported stable version.")
    return ".".join(str(int(part)) for part in match.groups())


def version_key(value: str) -> tuple[int, int, int]:
    normalized = normalize_version(value)
    return tuple(int(part) for part in normalized.split("."))  # type: ignore[return-value]


def parse_checksum(payload: bytes, expected_filename: str) -> str:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Checksum file is not UTF-8 text.") from exc
    for line in text.splitlines():
        match = re.fullmatch(r"\s*([0-9A-Fa-f]{64})\s+\*?([^\s]+)\s*", line)
        if not match:
            continue
        filename = match.group(2)
        if filename == expected_filename:
            return match.group(1).lower()
    raise ValueError("Checksum file does not contain the expected installer hash.")


def parse_latest_release(payload: dict, current_version: str) -> dict:
    if not isinstance(payload, dict) or payload.get("draft") is True or payload.get("prerelease") is True:
        raise ValueError("GitHub did not return a stable published release.")
    tag = str(payload.get("tag_name", "")).strip()
    latest_version = normalize_version(tag)
    normalized_current = normalize_version(current_version)
    installer_name = f"Oghma-Archive-Setup-{latest_version}.exe"
    checksum_name = f"{installer_name}.sha256"

    assets = payload.get("assets")
    if not isinstance(assets, list) or len(assets) > 100:
        raise ValueError("Release assets are missing or malformed.")
    by_name = {
        str(asset.get("name", "")): asset
        for asset in assets
        if isinstance(asset, dict) and asset.get("state") == "uploaded"
    }
    installer_asset = by_name.get(installer_name)
    checksum_asset = by_name.get(checksum_name)
    if not isinstance(installer_asset, dict) or not isinstance(checksum_asset, dict):
        raise ValueError("Release does not contain the required installer and checksum.")

    try:
        installer_size = int(installer_asset.get("size", 0))
        checksum_size = int(checksum_asset.get("size", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("Release asset size is invalid.") from exc
    if not 0 < installer_size <= MAX_INSTALLER_BYTES:
        raise ValueError("Installer size is outside the allowed range.")
    if not 0 < checksum_size <= MAX_CHECKSUM_BYTES:
        raise ValueError("Checksum size is outside the allowed range.")

    installer_url = _validated_asset_url(
        installer_asset.get("browser_download_url"), tag, installer_name
    )
    checksum_url = _validated_asset_url(
        checksum_asset.get("browser_download_url"), tag, checksum_name
    )
    asset_digest = str(installer_asset.get("digest", "")).strip().lower()
    if asset_digest:
        if not asset_digest.startswith("sha256:") or not SHA256_PATTERN.fullmatch(asset_digest[7:]):
            raise ValueError("GitHub asset digest is malformed.")
        asset_digest = asset_digest[7:]

    release_url = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPOSITORY}/releases/tag/{tag}"
    return {
        "current_version": normalized_current,
        "latest_version": latest_version,
        "available": version_key(latest_version) > version_key(normalized_current),
        "release_name": str(payload.get("name") or tag)[:160],
        "release_notes": str(payload.get("body") or "")[:4000],
        "published_at": str(payload.get("published_at") or "")[:64],
        "release_url": release_url,
        "installer_name": installer_name,
        "installer_size": installer_size,
        "_installer_url": installer_url,
        "_checksum_url": checksum_url,
        "_asset_digest": asset_digest,
    }


def public_release_payload(release: dict) -> dict:
    return {key: value for key, value in release.items() if not key.startswith("_")}


def _validated_asset_url(value, tag: str, filename: str) -> str:
    url = str(value or "").strip()
    parsed = urlsplit(url)
    expected_path = f"{RELEASE_DOWNLOAD_PREFIX}{tag}/{filename}"
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path != expected_path
    ):
        raise ValueError("Release asset URL is not approved.")
    return url


class UpdateManager:
    def __init__(
        self,
        data_dir: Path,
        bundle_root: Path,
        current_version: str,
        *,
        fetch_bytes: Callable = fetch_restricted,
        frozen: bool | None = None,
        executable: Path | None = None,
    ) -> None:
        self.data_dir = Path(data_dir).resolve()
        self.bundle_root = Path(bundle_root).resolve()
        self.current_version = normalize_version(current_version)
        self.update_dir = self.data_dir / ".updates"
        self.manifest_path = self.update_dir / "prepared.json"
        self.fetch_bytes = fetch_bytes
        self.frozen = getattr(sys, "frozen", False) if frozen is None else frozen
        self.executable = Path(executable or sys.executable).resolve()
        self._cached_release: dict | None = None
        self._cached_at = 0.0

    def local_status(self) -> dict:
        prepared = self._read_prepared_manifest(verify_hash=False)
        downloaded = bool(
            prepared
            and version_key(prepared["version"]) > version_key(self.current_version)
        )
        return {
            "ok": True,
            "current_version": self.current_version,
            "packaged": bool(self.frozen and os.name == "nt"),
            "downloaded": downloaded,
            "downloaded_version": prepared.get("version", "") if downloaded else "",
        }

    def check_latest(self, *, force: bool = False) -> dict:
        release = self._latest_release(force=force)
        result = public_release_payload(release)
        prepared = self._read_prepared_manifest(verify_hash=False)
        result.update(
            {
                "ok": True,
                "packaged": bool(self.frozen and os.name == "nt"),
                "downloaded": bool(
                    release["available"]
                    and prepared
                    and prepared.get("version") == release["latest_version"]
                ),
            }
        )
        return result

    def download_latest(self) -> dict:
        release = self._latest_release(force=True)
        if not release["available"]:
            result = public_release_payload(release)
            result.update(
                {
                    "ok": True,
                    "packaged": bool(self.frozen and os.name == "nt"),
                    "downloaded": False,
                }
            )
            return result

        checksum_payload = self._fetch(
            release["_checksum_url"],
            allowed_hosts=DOWNLOAD_HOSTS,
            content_types={"text/plain", "application/octet-stream"},
            maximum_bytes=MAX_CHECKSUM_BYTES,
            timeout_seconds=30,
        )
        try:
            expected_hash = parse_checksum(checksum_payload, release["installer_name"])
        except ValueError as exc:
            raise ExternalOperationError("Контрольная сумма релиза имеет неверный формат.") from exc
        if release["_asset_digest"] and release["_asset_digest"] != expected_hash:
            raise ExternalOperationError("SHA-256 в релизе GitHub не совпадает с файлом контрольной суммы.")

        installer_payload = self._fetch(
            release["_installer_url"],
            allowed_hosts=DOWNLOAD_HOSTS,
            content_types={"application/octet-stream", "application/x-msdownload"},
            maximum_bytes=MAX_INSTALLER_BYTES,
            timeout_seconds=15 * 60,
        )
        if len(installer_payload) != release["installer_size"]:
            raise ExternalOperationError(
                "Размер загруженного установщика не совпадает с данными релиза."
            )
        actual_hash = hashlib.sha256(installer_payload).hexdigest()
        if actual_hash != expected_hash:
            raise ExternalOperationError("Загруженный установщик не прошёл проверку SHA-256.")

        self.update_dir.mkdir(parents=True, exist_ok=True)
        installer_path = self.update_dir / release["installer_name"]
        self._write_atomic(installer_path, installer_payload)
        write_json(
            self.manifest_path,
            {
                "version": release["latest_version"],
                "filename": release["installer_name"],
                "sha256": actual_hash,
                "size": len(installer_payload),
                "release_url": release["release_url"],
            },
        )
        self._remove_obsolete_installers(installer_path)

        result = public_release_payload(release)
        result.update(
            {
                "ok": True,
                "packaged": bool(self.frozen and os.name == "nt"),
                "downloaded": True,
                "downloaded_bytes": len(installer_payload),
            }
        )
        return result

    def launch_prepared_installer(self) -> dict:
        if os.name != "nt" or not self.frozen:
            raise ConflictError("Запуск обновления доступен только в установленной версии Oghma.")
        prepared = self._read_prepared_manifest(verify_hash=True)
        if prepared is None:
            raise ConflictError("Сначала загрузите и проверьте обновление.")
        if version_key(prepared["version"]) <= version_key(self.current_version):
            raise ConflictError("Загруженная версия не новее установленной.")

        installer_path = self.update_dir / prepared["filename"]
        helper_candidates = (
            self.executable.parent / "installer" / "launch-update.ps1",
            self.bundle_root / "installer" / "launch-update.ps1",
        )
        helper_path = next((path for path in helper_candidates if path.is_file()), None)
        if helper_path is None:
            raise ExternalOperationError("Служебный модуль обновления не найден.")

        command = [
            str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(helper_path),
            "-InstallerPath",
            str(installer_path),
            "-OghmaExePath",
            str(self.executable),
            "-TrayProcessId",
            str(os.getppid()),
            "-ServerProcessId",
            str(os.getpid()),
            "-ExpectedSha256",
            prepared["sha256"],
        ]
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            subprocess.Popen(
                command,
                cwd=str(self.executable.parent),
                creationflags=creationflags,
                close_fds=True,
            )
        except OSError as exc:
            raise ExternalOperationError("Не удалось запустить мастер обновления.") from exc
        return {
            "ok": True,
            "installing": True,
            "version": prepared["version"],
            "message": "Oghma будет закрыта, после чего откроется мастер обновления.",
        }

    def _latest_release(self, *, force: bool) -> dict:
        now = time.monotonic()
        if not force and self._cached_release is not None and now - self._cached_at < CACHE_SECONDS:
            return self._cached_release.copy()
        request = Request(
            LATEST_RELEASE_API,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
                "User-Agent": f"Oghma-Archive/{self.current_version}",
            },
        )
        raw = self._fetch(
            request.full_url,
            request=request,
            allowed_hosts=API_HOSTS,
            content_types={"application/json"},
            maximum_bytes=MAX_RELEASE_JSON_BYTES,
            timeout_seconds=20,
        )
        try:
            payload = json.loads(raw.decode("utf-8"))
            release = parse_latest_release(payload, self.current_version)
        except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise ExternalOperationError("GitHub вернул некорректные данные релиза Oghma.") from exc
        self._cached_release = release.copy()
        self._cached_at = now
        return release

    def _fetch(
        self,
        url: str,
        *,
        allowed_hosts: set[str],
        content_types: set[str],
        maximum_bytes: int,
        timeout_seconds: float,
        request: Request | None = None,
    ) -> bytes:
        outgoing = request or Request(
            url,
            headers={"User-Agent": f"Oghma-Archive/{self.current_version}"},
        )
        try:
            return self.fetch_bytes(
                outgoing,
                allowed_hosts=allowed_hosts,
                allowed_content_types=content_types,
                maximum_bytes=maximum_bytes,
                timeout_seconds=timeout_seconds,
            )
        except HTTPError as exc:
            if exc.code == 404:
                raise ExternalOperationError("В GitHub пока нет опубликованного релиза Oghma.") from exc
            if exc.code in {403, 429}:
                raise ExternalOperationError("GitHub временно ограничил проверку обновлений. Повторите позже.") from exc
            raise ExternalOperationError("GitHub не ответил на запрос обновления.") from exc
        except (URLError, OSError, ExternalHttpRejected) as exc:
            raise ExternalOperationError("Не удалось безопасно подключиться к GitHub Releases.") from exc

    def _read_prepared_manifest(self, *, verify_hash: bool) -> dict | None:
        try:
            manifest = read_json(self.manifest_path, fallback=None)
        except JsonIntegrityError:
            return None
        if not isinstance(manifest, dict):
            return None
        try:
            version = normalize_version(manifest.get("version", ""))
            filename = str(manifest.get("filename", ""))
            expected_name = f"Oghma-Archive-Setup-{version}.exe"
            expected_hash = str(manifest.get("sha256", "")).lower()
            expected_size = int(manifest.get("size", 0))
        except (TypeError, ValueError):
            return None
        if filename != expected_name or not SHA256_PATTERN.fullmatch(expected_hash):
            return None
        if not 0 < expected_size <= MAX_INSTALLER_BYTES:
            return None
        path = (self.update_dir / filename).resolve()
        if path.parent != self.update_dir.resolve() or not path.is_file():
            return None
        try:
            if path.stat().st_size != expected_size:
                return None
            if verify_hash and self._hash_file(path) != expected_hash:
                return None
        except OSError:
            return None
        return {**manifest, "version": version, "filename": filename, "sha256": expected_hash}

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _write_atomic(path: Path, payload: bytes) -> None:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{path.name}.",
                suffix=".part",
                dir=path.parent,
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def _remove_obsolete_installers(self, keep: Path) -> None:
        for candidate in self.update_dir.glob("Oghma-Archive-Setup-*.exe"):
            if candidate != keep and candidate.is_file():
                candidate.unlink(missing_ok=True)
