"""
İş kuyruğu. Thread-safe in-memory kuyruk: pending → processing → done/failed.
"""
from __future__ import annotations

import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Job:
    id: str
    filename: str
    filepath: str
    status: str  # pending | processing | done | failed
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    report: dict | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "filepath": self.filepath,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "error": self.error,
        }


class JobQueue:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: deque[Job] = deque()
        self._processing: dict[str, Job] = {}
        self._done: list[Job] = []

    def enqueue(self, filename: str, filepath: str) -> Job:
        job = Job(
            id=str(uuid.uuid4()),
            filename=filename,
            filepath=filepath,
            status="pending",
            created_at=datetime.now(),
        )
        with self._lock:
            self._pending.append(job)
        return job

    def next_pending(self) -> Job | None:
        with self._lock:
            if not self._pending:
                return None
            return self._pending[0]

    def mark_processing(self, job_id: str) -> None:
        with self._lock:
            if self._pending and self._pending[0].id == job_id:
                job = self._pending.popleft()
                job.status = "processing"
                job.started_at = datetime.now()
                self._processing[job_id] = job

    def mark_done(self, job_id: str, report: dict) -> None:
        with self._lock:
            job = self._processing.pop(job_id, None)
            if job:
                job.status = "done"
                job.finished_at = datetime.now()
                job.report = report
                self._done.append(job)

    def mark_failed(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._processing.pop(job_id, None)
            if job:
                job.status = "failed"
                job.finished_at = datetime.now()
                job.error = error
                self._done.append(job)

    def get_job(self, job_id: str) -> Job | None:
        with self._lock:
            for j in self._pending:
                if j.id == job_id:
                    return j
            if job_id in self._processing:
                return self._processing[job_id]
            for j in self._done:
                if j.id == job_id:
                    return j
        return None

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "pending": [j.to_dict() for j in self._pending],
                "processing": [j.to_dict() for j in self._processing.values()],
                "done": [j.to_dict() for j in self._done],
                "counts": {
                    "pending": len(self._pending),
                    "processing": len(self._processing),
                    "done": sum(1 for j in self._done if j.status == "done"),
                    "failed": sum(1 for j in self._done if j.status == "failed"),
                },
            }
