from __future__ import annotations

import asyncio

from celery import Celery

from app import actions, config
from app.entities import Namespace, RelocationPath, RelocationResult

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


@celery_app.task
def ping() -> str:
    return "pong"


@celery_app.task
def move_batch(
    namespace: Namespace, relocations: list[RelocationPath]
) -> list[RelocationResult]:
    async def _move_batch(
        namespace: Namespace, relocations: list[RelocationPath]
    ) -> list[RelocationResult]:
        import edgedb

        async with edgedb.create_async_pool(
            dsn=config.EDGEDB_DSN,
            min_size=4,
            max_size=4,
        ) as pool:
            return await actions.move_batch(pool, namespace, relocations)

    result = asyncio.run(_move_batch(namespace, relocations))
    return result
