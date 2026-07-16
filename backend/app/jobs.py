from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from threading import Lock
from uuid import uuid4


class JobStatus(StrEnum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BackgroundRemovalJob:
    id: str
    input_key: str
    status: JobStatus
    result_key: str | None = None
    result_url: str | None = None
    error: str | None = None

    def to_public_dict(self) -> dict[str, str | None]:
        return {
            "id": self.id,
            "inputKey": self.input_key,
            "status": self.status.value,
            "resultKey": self.result_key,
            "resultUrl": self.result_url,
            "error": self.error,
        }


class InMemoryJobStore:
    """Keeps synchronous job status available for the lifetime of one API process."""

    def __init__(self) -> None:
        self._jobs: dict[str, BackgroundRemovalJob] = {}
        self._lock = Lock()

    def create(self, input_key: str) -> BackgroundRemovalJob:
        job = BackgroundRemovalJob(
            id=uuid4().hex,
            input_key=input_key,
            status=JobStatus.PROCESSING,
        )
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> BackgroundRemovalJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def complete(self, job: BackgroundRemovalJob, result_key: str, result_url: str) -> None:
        with self._lock:
            job.status = JobStatus.COMPLETED
            job.result_key = result_key
            job.result_url = result_url

    def fail(self, job: BackgroundRemovalJob, error: str) -> None:
        with self._lock:
            job.status = JobStatus.FAILED
            job.error = error
