from __future__ import annotations

import pytest
from arq.connections import ArqRedis

from app.config import ARQWorkerConfig, config


@pytest.fixture(scope="session")
def arq_worker_config() -> ARQWorkerConfig:
    """ARQWorkerConfig with database set to 11."""
    worker_config = config.worker.copy()
    worker_config.broker_dsn.path = "/11"
    return worker_config


@pytest.fixture(scope="module")
async def arq_worker_pool():
    """ARQ worker pool."""
    async with ArqRedis.from_url(config.worker.broker_dsn) as pool:
        yield pool
