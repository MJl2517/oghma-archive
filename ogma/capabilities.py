from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from ogma.errors import ValidationError


@dataclass(frozen=True)
class FileCapability:
    path: Path
    expires_at: float


class FileCapabilityStore:
    """Short-lived approval for a file selected by a native picker."""

    def __init__(self, lifetime_seconds: int = 15 * 60, maximum_entries: int = 128) -> None:
        self.lifetime_seconds = lifetime_seconds
        self.maximum_entries = maximum_entries
        self._entries: dict[str, FileCapability] = {}
        self._lock = threading.RLock()

    def issue(self, selected_path: str | Path) -> tuple[str, str]:
        path = Path(selected_path).resolve(strict=True)
        if not path.is_file():
            raise ValidationError("The selected resource is not a regular file.")
        token = secrets.token_urlsafe(32)
        now = time.monotonic()
        with self._lock:
            self._purge_expired(now)
            while len(self._entries) >= self.maximum_entries:
                oldest = min(self._entries, key=lambda key: self._entries[key].expires_at)
                self._entries.pop(oldest, None)
            self._entries[token] = FileCapability(path, now + self.lifetime_seconds)
        return token, path.name

    def consume(self, token: str) -> Path:
        clean_token = str(token or "").strip()
        if not clean_token:
            raise ValidationError("A native file selection is required.")
        now = time.monotonic()
        with self._lock:
            self._purge_expired(now)
            capability = self._entries.pop(clean_token, None)
        if capability is None:
            raise ValidationError("File selection expired; choose the file again.")
        try:
            path = capability.path.resolve(strict=True)
        except OSError as exc:
            raise ValidationError("Selected file is no longer available.") from exc
        if not path.is_file():
            raise ValidationError("Selected resource is not a regular file.")
        return path

    def _purge_expired(self, now: float) -> None:
        expired = [
            token
            for token, capability in self._entries.items()
            if capability.expires_at <= now
        ]
        for token in expired:
            self._entries.pop(token, None)


class DirectoryCapabilityStore(FileCapabilityStore):
    """Short-lived approval for a directory selected by a native picker."""

    def issue(self, selected_path: str | Path) -> tuple[str, str]:
        path = Path(selected_path).resolve(strict=True)
        if not path.is_dir():
            raise ValidationError("The selected path is not a directory.")
        token = secrets.token_urlsafe(32)
        now = time.monotonic()
        with self._lock:
            self._purge_expired(now)
            while len(self._entries) >= self.maximum_entries:
                oldest = min(self._entries, key=lambda key: self._entries[key].expires_at)
                self._entries.pop(oldest, None)
            self._entries[token] = FileCapability(path, now + self.lifetime_seconds)
        return token, path.name or "Foundry Data"

    def consume(self, token: str) -> Path:
        clean_token = str(token or "").strip()
        if not clean_token:
            raise ValidationError("A native directory selection is required.")
        now = time.monotonic()
        with self._lock:
            self._purge_expired(now)
            capability = self._entries.pop(clean_token, None)
        if capability is None:
            raise ValidationError("Directory selection expired; choose it again.")
        try:
            path = capability.path.resolve(strict=True)
        except OSError as exc:
            raise ValidationError("Selected directory is no longer available.") from exc
        if not path.is_dir():
            raise ValidationError("Selected directory is no longer available.")
        return path
