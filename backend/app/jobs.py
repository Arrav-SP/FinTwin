from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4


class JobManager:
    """Run long workloads off the request thread and let callers poll for the outcome.

    Jobs run strictly one at a time: two workloads executing together would load the same
    database and contaminate each other's measurements. Jobs are held in memory, so they
    are lost when the server restarts; the experiments they produced stay in PostgreSQL.
    """

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fintwin-job")
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}

    def submit(self, kind: str, request: dict[str, Any], work: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        job_id = uuid4().hex
        job = {"job_id": job_id, "kind": kind, "status": "queued", "request": request, "submitted_at": _now(), "started_at": None, "finished_at": None, "result": None, "error": None}
        with self._lock:
            self._jobs[job_id] = job
        self._executor.submit(self._run, job_id, work)
        return self.get(job_id)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(job) for job in reversed(self._jobs.values())]

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            self._jobs[job_id].update(changes)

    def _run(self, job_id: str, work: Callable[[], dict[str, Any]]) -> None:
        self._update(job_id, status="running", started_at=_now())
        try:
            result = work()
        except Exception as exc:
            self._update(job_id, status="failed", error=str(exc)[:2000], finished_at=_now())
        else:
            self._update(job_id, status="completed", result=result, finished_at=_now())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
