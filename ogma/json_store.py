import json
import os
import shutil
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path


_LOCKS_GUARD = threading.Lock()
_PATH_LOCKS: dict[Path, threading.RLock] = {}


class JsonIntegrityError(RuntimeError):
    """A JSON document is corrupt and may need recovery from its backup."""


class JsonStoreLockedError(RuntimeError):
    """Another process is currently writing the same JSON document."""


def read_json(path: Path, fallback=None):
    if fallback is None:
        fallback = {}
    if not path.exists():
        return fallback

    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        backup_path = path.with_name(f"{path.name}.bak")
        raise JsonIntegrityError(
            f"Cannot read JSON data from {path}. "
            f"The file was not changed; recovery backup: {backup_path}."
        ) from exc


def write_json(path: Path, payload) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _path_lock(path):
        temp_path: Path | None = None
        backup_temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{path.name}.",
                suffix=".tmp",
                dir=path.parent,
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

            if path.exists():
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    prefix=f".{path.name}.backup.",
                    suffix=".tmp",
                    dir=path.parent,
                    delete=False,
                ) as backup_handle:
                    backup_temp_path = Path(backup_handle.name)
                    with path.open("rb") as source:
                        shutil.copyfileobj(source, backup_handle)
                    backup_handle.flush()
                    os.fsync(backup_handle.fileno())
                os.replace(backup_temp_path, path.with_name(f"{path.name}.bak"))
                backup_temp_path = None

            os.replace(temp_path, path)
            temp_path = None
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            if backup_temp_path is not None:
                backup_temp_path.unlink(missing_ok=True)


@contextmanager
def _path_lock(path: Path):
    resolved = path.resolve()
    with _LOCKS_GUARD:
        lock = _PATH_LOCKS.setdefault(resolved, threading.RLock())
    with lock:
        lock_path = path.with_name(f".{path.name}.lock")
        with lock_path.open("a+b") as handle:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            try:
                _lock_file(handle)
            except OSError as exc:
                raise JsonStoreLockedError(
                    f"Another process is writing JSON data to {path}; no data was changed."
                ) from exc
            try:
                yield
            finally:
                _unlock_file(handle)


def _lock_file(handle) -> None:
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_file(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
