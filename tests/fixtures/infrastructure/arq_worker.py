from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

import pytest
from arq.connections import ArqRedis

from app.config import ARQWorkerConfig, config


@pytest.fixture(scope="session")
def arq_worker_config() -> ARQWorkerConfig:
    """ARQWorkerConfig with database set to 11."""
    worker_config = config.worker.model_copy()
    scheme, netloc, _, query, fragments = urlsplit(worker_config.broker_dsn)
    dsn = urlunsplit((scheme, netloc, "/11", query, fragments))
    worker_config.broker_dsn = dsn
    return worker_config


@pytest.fixture(scope="module")
async def arq_worker_pool():
    """ARQ worker pool."""
    async with ArqRedis.from_url(config.worker.broker_dsn) as pool:
        yield pool
