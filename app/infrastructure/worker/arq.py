from __future__ import annotations

from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Self, assert_never

from arq.connections import ArqRedis
from arq.jobs import Job as ArqJob
from arq.jobs import JobStatus as ArqJobStatus

from app.app.infrastructure.worker import Job, JobStatus

if TYPE_CHECKING:
    from app.config import ARQWorkerConfig


class ARQWorker:
    __slots__ = ("pool", "_stack")

    def __init__(self, worker_config: ARQWorkerConfig):
        self.pool: ArqRedis = ArqRedis.from_url(str(worker_config.broker_dsn))
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> Self:
        await self._stack.enter_async_context(self.pool)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._stack.aclose()

    async def enqueue(self, job_name: str, *args, **kwargs) -> Job:
        job = await self.pool.enqueue_job(job_name, *args, **kwargs)
        assert job is not None
        return Job(id=job.job_id)

    async def get_result(self, job_id: str, *, timeout: int | float | None = 5):
        job = ArqJob(job_id=job_id, redis=self.pool)
        return await job.result(timeout=timeout)

    async def get_status(self, job_id: str) -> JobStatus:
        job = ArqJob(job_id=job_id, redis=self.pool)
        status = await job.status()
        match status:
            case ArqJobStatus.deferred \
                | ArqJobStatus.queued \
                | ArqJobStatus.in_progress \
                | ArqJobStatus.not_found:
                return JobStatus.pending
            case ArqJobStatus.complete:
                return JobStatus.complete
            case _:  # pragma: no cover
                assert_never(status)
