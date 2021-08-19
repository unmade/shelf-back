from __future__ import annotations

import asyncio
import functools
import logging
from typing import TYPE_CHECKING

import edgedb
from celery import Celery

from app import actions, config, db, errors
from app.entities import File, RelocationResult

if TYPE_CHECKING:
    from app.entities import Namespace, RelocationPath
    from app.typedefs import StrOrPath

logger = logging.getLogger(__name__)

celery_app = Celery(__name__)


class CeleryConfig:
    broker_url = config.CELERY_BROKER_DSN
    result_backend = config.CELERY_BACKEND_DSN
    task_serializer = "pickle"
    result_serializer = "pickle"
    event_serializer = "json"
    accept_content = ["application/json", "application/x-python-serialize"]
    result_accept_content = ["application/json", "application/x-python-serialize"]


celery_app.config_from_object(CeleryConfig)


@celery_app.task
def ping() -> str:
    return "pong"


def asynctask(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return celery_app.task(wrapper)


@asynctask
async def move(namespace: Namespace, relocation: RelocationPath) -> RelocationResult:
    path, next_path = relocation.from_path, relocation.to_path
    file, err_code = None, None

    async with db.connect() as conn:
        try:
            file = await actions.move(conn, namespace, path, next_path)
        except errors.Error as exc:
            err_code = exc.code
        except Exception:
            err_code = errors.ErrorCode.internal
            logger.exception("Failed to move file")

    return RelocationResult(file=file, err_code=err_code)


@asynctask
async def move_batch(
    namespace: Namespace,
    relocations: list[RelocationPath],
) -> list[RelocationResult]:
    async with edgedb.create_async_pool(
        dsn=config.DATABASE_DSN,
        min_size=2,
        max_size=2,
        tls_ca_file=config.DATABASE_TLS_CA_FILE,
    ) as pool:
        return await actions.move_batch(pool, namespace, relocations)


@asynctask
async def move_to_trash_batch(
    namespace: Namespace, paths: list[StrOrPath]
) -> list[RelocationResult]:
    """
    Move several files to trash asynchronously.

    Args:
        namespace (Namespace): Namespace, where files should be moved
        paths (list[StrOrPath]): List of file path to move.

    Returns:
        list[RelocationResult]: List, where each item contains either a moved file,
            or an error code.
    """
    async with edgedb.create_async_pool(
        dsn=config.DATABASE_DSN,
        min_size=2,
        max_size=2,
        tls_ca_file=config.DATABASE_TLS_CA_FILE,
    ) as pool:
        coros = (
            actions.move_to_trash(pool, namespace, path)
            for path in paths
        )
        items = await asyncio.gather(*coros, return_exceptions=True)

        for item in items:
            if isinstance(item, Exception) and not isinstance(item, errors.Error):
                logger.error("Error occured on moving file to trash", exc_info=item)

        return [
            RelocationResult(
                file=item if isinstance(item, File) else None,
                err_code=item.code if isinstance(item, errors.Error) else None,
            )
            for item in items
        ]
