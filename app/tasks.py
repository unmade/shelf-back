from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

import edgedb
import nest_asyncio
from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown

from app import actions, config
from app.entities import Namespace, RelocationPath, RelocationResult

if TYPE_CHECKING:
    from app.typedefs import DBPool

nest_asyncio.apply()

celery_app = Celery(__name__)


class CeleryConfig:
    broker_url = config.CELERY_BACKEND_DSN
    result_backend = "rpc"
    task_serializer = "pickle"
    result_serializer = "pickle"
    event_serializer = "json"
    accept_content = ["application/json", "application/x-python-serialize"]
    result_accept_content = ["application/json", "application/x-python-serialize"]


celery_app.config_from_object(CeleryConfig)

_loop: Optional[asyncio.AbstractEventLoop] = None
_db_pool: Optional[DBPool] = None


@worker_process_init.connect
def init_worker(**kwargs):
    global _loop
    global _db_pool

    _loop = asyncio.get_event_loop()
    _db_pool = _loop.run_until_complete(
        edgedb.create_async_pool(
            dsn=config.EDGEDB_DSN,
            min_size=4,
            max_size=4,
        )
    )


@worker_process_shutdown.connect
def shutdown_worker(**kwargs):
    global _loop
    global _db_pool

    assert _loop is not None
    assert _db_pool is not None

    _loop.run_until_complete(_db_pool.aclose())
    _loop.close()

    _loop = None
    _db_pool = None


@celery_app.task
def ping() -> str:
    return "pong"


@celery_app.task
def move_batch(
    namespace: Namespace, relocations: list[RelocationPath]
) -> list[RelocationResult]:
    assert _loop is not None
    assert _db_pool is not None
    coro = actions.move_batch(_db_pool, namespace, relocations)
    return _loop.run_until_complete(coro)
