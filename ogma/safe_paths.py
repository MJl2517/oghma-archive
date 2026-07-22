from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath
from urllib.parse import unquote


class PathBoundaryError(ValueError):
    """An untrusted path attempted to escape its approved filesystem root."""


def normalize_relative_path(untrusted_relative_path: str) -> str:
    """Return a Windows-aware, slash-separated relative path without traversal."""

    value = _fully_unquote(str(untrusted_relative_path or "")).strip()
    if not value or any(ord(character) < 32 for character in value):
        raise PathBoundaryError("Path is empty or contains control characters.")

    value = value.replace("\\", "/")
    if value.startswith(("/", "//")) or ":" in value:
        raise PathBoundaryError("Absolute, UNC, device, drive, and ADS paths are forbidden.")

    windows_path = PureWindowsPath(value)
    if windows_path.is_absolute() or windows_path.drive or windows_path.root:
        raise PathBoundaryError("Absolute Windows paths are forbidden.")

    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise PathBoundaryError("Relative traversal and ambiguous path components are forbidden.")
    return "/".join(parts)


def resolve_under(root: Path, untrusted_relative_path: str, expected: str = "file") -> Path:
    """Resolve an existing file/directory below root after Windows-aware validation."""

    value = normalize_relative_path(untrusted_relative_path)
    parts = value.split("/")

    root_resolved = Path(root).resolve(strict=True)
    candidate = root_resolved.joinpath(*parts).resolve(strict=True)
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise PathBoundaryError("Resolved path escapes its approved root.") from exc

    if expected == "file" and not candidate.is_file():
        raise PathBoundaryError("Expected a regular file.")
    if expected == "directory" and not candidate.is_dir():
        raise PathBoundaryError("Expected a directory.")
    if expected not in {"file", "directory", "any"}:
        raise ValueError(f"Unsupported expected path type: {expected}")
    return candidate


def resolve_destination_under(root: Path, untrusted_relative_path: str) -> Path:
    """Resolve a possibly-new destination below root, checking every existing prefix."""

    parts = normalize_relative_path(untrusted_relative_path).split("/")
    root_resolved = Path(root).resolve(strict=True)
    candidate = root_resolved
    for index, part in enumerate(parts):
        next_candidate = candidate / part
        if next_candidate.exists():
            candidate = next_candidate.resolve(strict=True)
            try:
                candidate.relative_to(root_resolved)
            except ValueError as exc:
                raise PathBoundaryError("Resolved path escapes its approved root.") from exc
            continue
        candidate = next_candidate.joinpath(*parts[index + 1 :])
        try:
            candidate.relative_to(root_resolved)
        except ValueError as exc:
            raise PathBoundaryError("Destination escapes its approved root.") from exc
        break
    return candidate


def resolve_relative_directory(root: Path, untrusted_relative_path: str) -> Path:
    return resolve_under(root, untrusted_relative_path, expected="directory")


def _fully_unquote(value: str) -> str:
    current = value
    for _ in range(4):
        decoded = unquote(current, errors="strict")
        if decoded == current:
            return decoded
        current = decoded
    if "%" in current:
        raise PathBoundaryError("Repeated URL encoding is forbidden.")
    return current
