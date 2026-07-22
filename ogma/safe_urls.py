from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


class UnsafeUrl(ValueError):
    pass


@dataclass(frozen=True)
class ExternalHttpUrl:
    value: str

    @classmethod
    def parse(cls, raw_value: str) -> "ExternalHttpUrl":
        value = str(raw_value or "").strip()
        if (
            not value
            or value.startswith("//")
            or "\\" in value
            or any(ord(character) < 32 for character in value)
        ):
            raise UnsafeUrl("External URL is empty or ambiguous.")
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except ValueError as exc:
            raise UnsafeUrl("External URL is malformed.") from exc
        if parsed.scheme.lower() not in {"http", "https"}:
            raise UnsafeUrl("Only http and https URLs are allowed.")
        if not parsed.hostname or parsed.username is not None or parsed.password is not None:
            raise UnsafeUrl("URL credentials and missing hosts are forbidden.")
        if port is not None and not 1 <= port <= 65535:
            raise UnsafeUrl("URL port is invalid.")
        return cls(value)


@dataclass(frozen=True)
class InternalPath:
    value: str

    @classmethod
    def parse(cls, raw_value: str) -> "InternalPath":
        value = str(raw_value or "").strip()
        if (
            not value.startswith("/")
            or value.startswith("//")
            or "\\" in value
            or any(ord(character) < 32 for character in value)
        ):
            raise UnsafeUrl("Internal path must start with exactly one slash.")
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc:
            raise UnsafeUrl("Internal path cannot contain an external origin.")
        return cls(value)


@dataclass(frozen=True)
class EntityReference:
    type: str
    id: str

    def __post_init__(self) -> None:
        if not self.type.strip() or not self.id.strip():
            raise ValueError("Entity reference requires a type and id.")
