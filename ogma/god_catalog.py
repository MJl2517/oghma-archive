from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request

from ogma.errors import ExternalOperationError, ValidationError
from ogma.external_http import ExternalHttpRejected, fetch_restricted
from ogma.json_store import JsonIntegrityError, JsonStoreLockedError, read_json, write_json
from ogma.security import json_within_limits
from ogma.updater import GITHUB_OWNER, GITHUB_REPOSITORY


CATALOG_SCHEMA = "ogma.gods.catalog.v1"
PACK_SCHEMA = "ogma.gods.export.v1"
INSTALL_STATE_SCHEMA = "ogma.gods.install-state.v1"
RAW_GITHUB_HOSTS = {"raw.githubusercontent.com"}
RAW_GITHUB_ROOT = (
    f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPOSITORY}/main/"
    "materials/gods"
)
CATALOG_URL = f"{RAW_GITHUB_ROOT}/manifest.json"
REPOSITORY_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPOSITORY}/tree/main/materials/gods"
MAX_CATALOG_BYTES = 512 * 1024
MAX_PACK_BYTES = 16 * 1024 * 1024
MAX_PACKS = 50
MAX_SELECTED_PACKS = 20
CACHE_SECONDS = 5 * 60
PACK_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
PACK_FILENAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,95}\.json$")
PACK_VERSION_PATTERN = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]{0,31}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _clean_text(value, *, field: str, maximum: int) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum or any(ord(character) < 32 for character in text):
        raise ValueError(f"God catalog field {field} is invalid.")
    return text


def parse_god_catalog(payload: object) -> list[dict]:
    if not isinstance(payload, dict) or payload.get("schema") != CATALOG_SCHEMA:
        raise ValueError("God catalog schema is not supported.")
    raw_packs = payload.get("packs")
    if not isinstance(raw_packs, list) or not raw_packs or len(raw_packs) > MAX_PACKS:
        raise ValueError("God catalog does not contain a valid pack list.")

    packs: list[dict] = []
    known_ids: set[str] = set()
    known_filenames: set[str] = set()
    for raw_pack in raw_packs:
        if not isinstance(raw_pack, dict):
            raise ValueError("God catalog pack is malformed.")
        pack_id = _clean_text(raw_pack.get("id"), field="id", maximum=64)
        filename = _clean_text(raw_pack.get("filename"), field="filename", maximum=100)
        version = _clean_text(raw_pack.get("version"), field="version", maximum=32)
        digest = str(raw_pack.get("sha256", "")).strip().lower()
        if not PACK_ID_PATTERN.fullmatch(pack_id) or not PACK_FILENAME_PATTERN.fullmatch(filename):
            raise ValueError("God pack path is invalid.")
        if not PACK_VERSION_PATTERN.fullmatch(version) or not SHA256_PATTERN.fullmatch(digest):
            raise ValueError("God pack version or checksum is invalid.")
        if pack_id in known_ids or filename in known_filenames:
            raise ValueError("God catalog contains duplicate packs.")
        try:
            file_size = int(raw_pack.get("size", 0))
            gods_count = int(raw_pack.get("gods_count", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("God pack size or item count is invalid.") from exc
        if not 1 <= file_size <= MAX_PACK_BYTES or not 1 <= gods_count <= 10_000:
            raise ValueError("God pack size or item count is outside the allowed range.")
        raw_pantheons = raw_pack.get("pantheons", [])
        if not isinstance(raw_pantheons, list) or not raw_pantheons or len(raw_pantheons) > 40:
            raise ValueError("God pack pantheon list is invalid.")
        pantheons = [_clean_text(value, field="pantheon", maximum=120) for value in raw_pantheons]
        packs.append(
            {
                "id": pack_id,
                "title": _clean_text(raw_pack.get("title"), field="title", maximum=120),
                "description": _clean_text(raw_pack.get("description"), field="description", maximum=500),
                "version": version,
                "language": _clean_text(raw_pack.get("language", "ru"), field="language", maximum=16),
                "gods_count": gods_count,
                "pantheons": pantheons,
                "filename": filename,
                "size": file_size,
                "sha256": digest,
            }
        )
        known_ids.add(pack_id)
        known_filenames.add(filename)
    return packs


class GodCatalogManager:
    def __init__(
        self,
        data_dir: Path,
        bundle_root: Path,
        app_version: str,
        *,
        fetch_bytes: Callable = fetch_restricted,
        frozen: bool | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.bundle_root = Path(bundle_root)
        self.app_version = str(app_version)
        self.fetch_bytes = fetch_bytes
        self.frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
        self.bundled_root = self.bundle_root / "materials" / "gods"
        self.state_path = self.data_dir / "installed-god-pantheons.json"
        self._cached_catalog: list[dict] | None = None
        self._cached_source = ""
        self._cached_at = 0.0

    def catalog(self, campaign_slug: str, *, force: bool = False) -> dict:
        packs, source = self._load_catalog(force=force)
        state = self._load_install_state()
        campaigns = state.get("campaigns", {})
        campaign_state = campaigns.get(campaign_slug, {}) if isinstance(campaigns, dict) else {}
        installed = campaign_state.get("installed", {}) if isinstance(campaign_state, dict) else {}
        public_packs = []
        for pack in packs:
            installed_pack = installed.get(pack["id"], {}) if isinstance(installed, dict) else {}
            installed_version = str(installed_pack.get("version", "")) if isinstance(installed_pack, dict) else ""
            public_packs.append(
                {
                    "id": pack["id"],
                    "title": pack["title"],
                    "description": pack["description"],
                    "version": pack["version"],
                    "language": pack["language"],
                    "gods_count": pack["gods_count"],
                    "pantheons": pack["pantheons"],
                    "installed": installed_version == pack["version"],
                    "installed_version": installed_version,
                    "update_available": bool(installed_version and installed_version != pack["version"]),
                }
            )
        return {
            "ok": True,
            "source": source,
            "repository_url": REPOSITORY_URL,
            "packs": public_packs,
        }

    def download_packs(self, pack_ids: object) -> list[dict]:
        selected_ids = self._normalize_selection(pack_ids)
        packs, source = self._load_catalog(force=False)
        by_id = {pack["id"]: pack for pack in packs}
        if any(pack_id not in by_id for pack_id in selected_ids):
            raise ValidationError("Выбранного пантеона больше нет в каталоге. Обновите список.")

        downloaded = []
        for pack_id in selected_ids:
            entry = by_id[pack_id]
            raw = self._load_pack_bytes(entry, source)
            if len(raw) != entry["size"]:
                raise ExternalOperationError(f"Размер набора «{entry['title']}» не совпадает с манифестом.")
            if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                raise ExternalOperationError(f"Контрольная сумма набора «{entry['title']}» не совпадает.")
            try:
                payload = json.loads(raw.decode("utf-8-sig"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise ExternalOperationError(f"Набор «{entry['title']}» содержит некорректный JSON.") from exc
            if not json_within_limits(payload):
                raise ExternalOperationError(f"Набор «{entry['title']}» слишком сложный для безопасного импорта.")
            if (
                not isinstance(payload, dict)
                or payload.get("schema") != PACK_SCHEMA
                or not isinstance(payload.get("gods"), list)
                or len(payload["gods"]) != entry["gods_count"]
            ):
                raise ExternalOperationError(f"Набор «{entry['title']}» не соответствует манифесту.")
            downloaded.append({"entry": entry.copy(), "payload": payload})
        return downloaded

    def record_installed(self, campaign_slug: str, entries: list[dict]) -> None:
        state = self._load_install_state()
        campaigns = state.setdefault("campaigns", {})
        campaign_state = campaigns.setdefault(campaign_slug, {})
        installed = campaign_state.setdefault("installed", {})
        installed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for entry in entries:
            installed[entry["id"]] = {
                "version": entry["version"],
                "installed_at": installed_at,
                "gods_count": entry["gods_count"],
            }
        try:
            write_json(self.state_path, state)
        except (OSError, JsonStoreLockedError):
            return

    def _normalize_selection(self, pack_ids: object) -> list[str]:
        if not isinstance(pack_ids, list) or not pack_ids or len(pack_ids) > MAX_SELECTED_PACKS:
            raise ValidationError("Выберите от одного до двадцати наборов пантеонов.")
        selected: list[str] = []
        for raw_pack_id in pack_ids:
            pack_id = str(raw_pack_id or "").strip()
            if not PACK_ID_PATTERN.fullmatch(pack_id):
                raise ValidationError("Выбран некорректный набор пантеона.")
            if pack_id not in selected:
                selected.append(pack_id)
        return selected

    def _load_catalog(self, *, force: bool) -> tuple[list[dict], str]:
        now = time.monotonic()
        if not force and self._cached_catalog is not None and now - self._cached_at < CACHE_SECONDS:
            return [pack.copy() for pack in self._cached_catalog], self._cached_source
        if not self.frozen and (self.bundled_root / "manifest.json").is_file():
            packs, source = self._read_bundled_catalog(), "bundled"
        else:
            try:
                packs, source = self._read_remote_catalog(), "github"
            except ExternalOperationError:
                if not (self.bundled_root / "manifest.json").is_file():
                    raise
                packs, source = self._read_bundled_catalog(), "bundled"
        self._cached_catalog = [pack.copy() for pack in packs]
        self._cached_source = source
        self._cached_at = now
        return [pack.copy() for pack in packs], source

    def _read_remote_catalog(self) -> list[dict]:
        return self._parse_catalog_bytes(self._fetch(CATALOG_URL, MAX_CATALOG_BYTES))

    def _read_bundled_catalog(self) -> list[dict]:
        try:
            raw = (self.bundled_root / "manifest.json").read_bytes()
        except OSError as exc:
            raise ExternalOperationError("Не удалось открыть встроенный каталог пантеонов.") from exc
        if len(raw) > MAX_CATALOG_BYTES:
            raise ExternalOperationError("Встроенный каталог пантеонов слишком большой.")
        return self._parse_catalog_bytes(raw)

    def _parse_catalog_bytes(self, raw: bytes) -> list[dict]:
        try:
            payload = json.loads(raw.decode("utf-8-sig"))
            if not json_within_limits(payload):
                raise ValueError("God catalog exceeds JSON limits.")
            return parse_god_catalog(payload)
        except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise ExternalOperationError("Каталог пантеонов повреждён или использует неподдерживаемый формат.") from exc

    def _load_pack_bytes(self, entry: dict, source: str) -> bytes:
        if source == "bundled":
            try:
                raw = (self.bundled_root / entry["filename"]).read_bytes()
            except OSError as exc:
                raise ExternalOperationError(f"Не удалось открыть набор «{entry['title']}».") from exc
            if len(raw) > MAX_PACK_BYTES:
                raise ExternalOperationError(f"Набор «{entry['title']}» слишком большой.")
            return raw
        return self._fetch(f"{RAW_GITHUB_ROOT}/{entry['filename']}", MAX_PACK_BYTES)

    def _fetch(self, url: str, maximum_bytes: int) -> bytes:
        request = Request(
            url,
            headers={
                "Accept": "application/json, text/plain;q=0.9, application/octet-stream;q=0.8",
                "User-Agent": f"Oghma-Archive/{self.app_version}",
            },
        )
        try:
            return self.fetch_bytes(
                request,
                allowed_hosts=RAW_GITHUB_HOSTS,
                allowed_content_types={"application/json", "text/plain", "application/octet-stream"},
                maximum_bytes=maximum_bytes,
                timeout_seconds=15,
            )
        except HTTPError as exc:
            if exc.code == 404:
                message = "Каталог пантеонов ещё не опубликован в GitHub."
            elif exc.code in {403, 429}:
                message = "GitHub временно ограничил загрузку пантеонов. Попробуйте позже."
            else:
                message = "GitHub не смог отдать каталог пантеонов."
            raise ExternalOperationError(message) from exc
        except (URLError, TimeoutError, ExternalHttpRejected, OSError) as exc:
            raise ExternalOperationError("Не удалось связаться с GitHub для загрузки пантеонов.") from exc

    def _load_install_state(self) -> dict:
        try:
            payload = read_json(self.state_path, fallback={})
        except (JsonIntegrityError, OSError):
            payload = {}
        if not isinstance(payload, dict) or payload.get("schema") != INSTALL_STATE_SCHEMA:
            return {"schema": INSTALL_STATE_SCHEMA, "campaigns": {}}
        return payload
