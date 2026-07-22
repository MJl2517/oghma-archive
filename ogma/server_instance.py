from __future__ import annotations

import os
import tempfile
from pathlib import Path


class ServerAlreadyRunningError(RuntimeError):
    pass


class ServerInstanceLock:
    """Process-wide lock keyed by the local HTTP port."""

    def __init__(self, port: int) -> None:
        self.port = int(port)
        self._handle = None
        self._stream = None

    def acquire(self) -> None:
        if os.name == "nt":
            self._acquire_windows()
        else:
            self._acquire_posix()

    def release(self) -> None:
        if self._handle is not None:
            import ctypes

            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None
        if self._stream is not None:
            try:
                import fcntl

                fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)
            finally:
                self._stream.close()
                self._stream = None

    def __enter__(self) -> "ServerInstanceLock":
        self.acquire()
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.release()

    def _acquire_windows(self) -> None:
        import ctypes
        from ctypes import wintypes

        create_mutex = ctypes.windll.kernel32.CreateMutexW
        create_mutex.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        create_mutex.restype = wintypes.HANDLE
        ctypes.windll.kernel32.SetLastError(0)
        handle = create_mutex(None, False, f"Local\\OgmaServer-{self.port}")
        last_error = ctypes.windll.kernel32.GetLastError()
        if not handle:
            raise OSError("Unable to create the Oghma server instance lock.")
        if last_error == 183:
            ctypes.windll.kernel32.CloseHandle(handle)
            raise ServerAlreadyRunningError(
                f"Another Oghma server already owns local port {self.port}."
            )
        self._handle = handle

    def _acquire_posix(self) -> None:
        import fcntl

        lock_path = Path(tempfile.gettempdir()) / f"ogma-server-{self.port}.lock"
        stream = lock_path.open("a+b")
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            stream.close()
            raise ServerAlreadyRunningError(
                f"Another Oghma server already owns local port {self.port}."
            ) from exc
        self._stream = stream
