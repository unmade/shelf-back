from __future__ import annotations

import asyncio
import functools
import logging
from typing import TYPE_CHECKING

from celery import Celery

from app import actions, config, db, errors
from app.entities import RelocationResult

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


def asynctask(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return celery_app.task(wrapper)


@celery_app.task
def ping() -> str:
    return "pong"


@asynctask
async def move_batch(
    namespace: Namespace,
    relocations: list[RelocationPath],
) -> list[RelocationResult]:
    """
    Move several files/folders to a different locations.

    Args:
        namespace (Namespace): Namespace, where files should be moved.
        relocations (Iterable[RelocationPath]): Iterable, where each item contains
            current file path and path to move file to.

    Returns:
        list[RelocationResult]: List, where each item contains either a moved file
            or an error code.
    """
    results = []
    async with db.connect() as conn:
        for relocation in relocations:
            path, next_path = relocation.from_path, relocation.to_path
            file, err_code = None, None

            try:
                file = await actions.move(conn, namespace, path, next_path)
            except errors.Error as exc:
                err_code = exc.code
            except Exception:
                err_code = errors.ErrorCode.internal
                logger.exception("Unexpectedly failed to move file")

            results.append(RelocationResult(file=file, err_code=err_code))
    return results


@asynctask
async def move_to_trash_batch(
    namespace: Namespace,
    paths: list[StrOrPath],
) -> list[RelocationResult]:
    """
    Move several files to trash asynchronously.

    Args:
        namespace (Namespace): Namespace, where files should be moved to trash
        paths (list[StrOrPath]): List of file path to move to trash.

    Returns:
        list[RelocationResult]: List, where each item contains either a moved file
            or an error code.
    """
    results = []
    async with db.connect() as conn:
        for path in paths:
            file, err_code = None, None
            try:
                file = await actions.move_to_trash(conn, namespace, path)
            except errors.Error as exc:
                err_code = exc.code
            except Exception:
                err_code = errors.ErrorCode.internal
                logger.exception("Unexpectedly failed to move file to trash")

            results.append(RelocationResult(file=file, err_code=err_code))
    return results
