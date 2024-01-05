from __future__ import annotations

import pytest
from arq.connections import ArqRedis
from arq.worker import Worker

from app.worker.main import WorkerSettings

pytestmark = [pytest.mark.anyio]


@pytest.fixture(scope="module")
async def worker(arq_worker_pool: ArqRedis):
    settings = {
        k: v
        for k, v in vars(WorkerSettings).items()
        if not k.startswith("__")
    }
    worker = Worker(
        burst=True,
        redis_pool=arq_worker_pool,
        poll_delay=0.01,
        **settings,
    )
    yield worker
    await worker.close()


class TestWorker:
    async def test(self, arq_worker_pool: ArqRedis, worker: Worker):
        # WHEN
        job = await arq_worker_pool.enqueue_job("ping")
        await worker.main()
        # THEN
        assert job is not None
        result = await job.result(timeout=1)
        assert result == "pong"
