from __future__ import annotations

import enum
from typing import Protocol, Self

__all__ = [
    "Job",
    "JobStatus",
    "IWorker",
]


class JobStatus(str, enum.Enum):
    pending = "pending"
    complete = "complete"


class Job:
    __slots__ = ("id", )

    def __init__(self, id: str):
        self.id = id


class IWorker(Protocol):
    async def __aenter__(self) -> Self:
        ...  # pragma: no cover

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        ...  # pragma: no cover

    async def enqueue(self, job_name: str, *args, **kwargs) -> Job:
        """Enqueue a job."""

    async def get_status(self, job_id: str) -> JobStatus:
        """Returns status for a given job_id."""

    async def get_result(self, job_id: str):
        """Returns result for a given job_id."""
