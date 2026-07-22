from __future__ import annotations

import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from ogma.errors import ApplicationError, ConflictError, NotFoundError


@dataclass
class LocalJob:
    id: str
    kind: str
    state: str = "queued"
    created_at: float = field(default_factory=time.monotonic)
    completed_at: float | None = None
    result: Any = None
    error: dict | None = None


class LocalJobBroker:
    """Single-flight broker for native dialogs and other blocking local work."""

    def __init__(self, retention_seconds: int = 15 * 60) -> None:
        self.retention_seconds = retention_seconds
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ogma-local-job")
        self._jobs: dict[str, LocalJob] = {}
        self._active_job_id = ""
        self._lock = threading.RLock()

    def start(self, kind: str, operation: Callable[[], Any]) -> str:
        with self._lock:
            self._purge()
            active = self._jobs.get(self._active_job_id)
            if active is not None and active.state in {"queued", "running"}:
                raise ConflictError("Another local operation is already running.")
            job_id = secrets.token_urlsafe(24)
            self._jobs[job_id] = LocalJob(id=job_id, kind=str(kind or "local_operation"))
            self._active_job_id = job_id
            self._executor.submit(self._run, job_id, operation)
            return job_id

    def status(self, job_id: str) -> dict:
        with self._lock:
            self._purge()
            job = self._jobs.get(str(job_id or ""))
            if job is None:
                raise NotFoundError("Local operation was not found.")
            payload = {
                "id": job.id,
                "kind": job.kind,
                "state": job.state,
            }
            if job.state == "succeeded":
                payload["result"] = job.result
            elif job.state == "failed":
                payload["error"] = job.error or {
                    "code": "external_operation_failed",
                    "message": "Local operation failed.",
                }
            return payload

    def _run(self, job_id: str, operation: Callable[[], Any]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.state = "running"
        try:
            result = operation()
        except ApplicationError as exc:
            error = {"code": exc.code, "message": exc.safe_message}
            self._finish(job_id, "failed", error=error)
        except Exception:
            self._finish(
                job_id,
                "failed",
                error={
                    "code": "external_operation_failed",
                    "message": "Local operation failed.",
                },
            )
        else:
            self._finish(job_id, "succeeded", result=result)

    def _finish(
        self,
        job_id: str,
        state: str,
        *,
        result: Any = None,
        error: dict | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.state = state
            job.result = result
            job.error = error
            job.completed_at = time.monotonic()
            if self._active_job_id == job_id:
                self._active_job_id = ""

    def _purge(self) -> None:
        now = time.monotonic()
        expired = [
            job_id
            for job_id, job in self._jobs.items()
            if job.completed_at is not None
            and now - job.completed_at > self.retention_seconds
        ]
        for job_id in expired:
            self._jobs.pop(job_id, None)
