from __future__ import annotations

import pytest
from arq.jobs import Job as ArqJob
from arq.worker import Worker

from app.app.infrastructure.worker import JobStatus
from app.config import config
from app.infrastructure.worker.arq import ARQWorker

pytestmark = [pytest.mark.anyio]


async def ping(ctx):
    return "pong"


@pytest.fixture(scope="module")
async def worker_cli():
    async with ARQWorker(config.worker) as worker:
        yield worker


@pytest.fixture(scope="module")
async def worker(worker_cli: ARQWorker):
    return Worker(
        functions=[ping],
        redis_pool=worker_cli.pool,
        poll_delay=0.01,
        burst=True,
    )


class TestEnqueue:
    async def test(self, worker_cli: ARQWorker, worker: Worker):
        # WHEN
        job = await worker_cli.enqueue("ping")
        # THEN
        await worker.main()
        result = await ArqJob(job.id, worker_cli.pool).result(timeout=1)
        assert result == "pong"


class TestGetResult:
    async def test(self, worker_cli: ARQWorker, worker: Worker):
        # GIVEN
        job = await worker_cli.enqueue("ping")
        await worker.main()
        # WHEN
        result = await worker_cli.get_result(job.id)
        # THEN
        assert result == "pong"


class TestGetStatus:
    async def test_complete(self, worker_cli: ARQWorker, worker: Worker):
        # GIVEN
        job = await worker_cli.enqueue("ping")
        await worker.main()
        # WHEN
        status = await worker_cli.get_status(job.id)
        # THEN
        assert status == JobStatus.complete

    async def test_pending(self, worker_cli: ARQWorker):
        status = await worker_cli.get_status("non-existing-job-id")
        assert status == JobStatus.pending
