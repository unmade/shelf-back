from __future__ import annotations

import asyncio
import functools
import logging
from typing import TYPE_CHECKING

from celery import Celery

from app import actions, config, db, errors
from app.entities import FileTaskResult
from app.infrastructure.database.edgedb.db import EdgeDBDatabase
from app.infrastructure.provider import Provider
from app.infrastructure.storage import FileSystemStorage, S3Storage

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.app.infrastructure import IStorage
    from app.entities import Namespace, RelocationPath
    from app.typedefs import StrOrPath

logger = logging.getLogger(__name__)

celery_app = Celery(__name__)


def _create_database() -> EdgeDBDatabase:
    return EdgeDBDatabase(
        dsn=config.DATABASE_DSN,
        max_concurrency=1,
        tls_ca_file=config.DATABASE_TLS_CA_FILE,
        tls_security=config.DATABASE_TLS_SECURITY,
    )


def _create_storage() -> IStorage:
    if config.STORAGE_TYPE == config.StorageType.s3:
        return S3Storage(
            location=config.STORAGE_LOCATION,
        )
    return FileSystemStorage(location=config.STORAGE_LOCATION)


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
async def delete_immediately_batch(
    namespace: Namespace,
    paths: Iterable[StrOrPath],
) -> list[FileTaskResult]:
    """
    Permanently delete a file or a folder with all of its contents.

    Args:
        namespace (Namespace): Namespace where file/folder should be deleted.
        paths (Iterable[StrOrPath]): Iterable of pathnames to delete.

    Returns:
        list[FileTaskResult]: List, where each item contains either a moved file
            or an error code.
    """
    results = []
    async with db.create_client() as conn:
        for path in paths:
            file, err_code = None, None

            try:
                file = await actions.delete_immediately(conn, namespace, path)
            except errors.FileNotFound:
                err_code = errors.ErrorCode.file_not_found
            except Exception:
                err_code = errors.ErrorCode.internal
                logger.exception("Unexpectedly failed to delete a file")

            results.append(FileTaskResult(file=file, err_code=err_code))
    return results


@asynctask
async def empty_trash(namespace: Namespace) -> None:
    """
    Delete all files and folders in the Trash folder within a target Namespace.

    Args:
        namespace (Namespace): Namespace where Trash should be emptied.
    """
    async with db.create_client() as conn:
        await actions.empty_trash(conn, namespace)


@asynctask
async def move_batch(
    ns_path: StrOrPath,
    relocations: Iterable[RelocationPath],
) -> list[FileTaskResult]:
    """
    Move several files/folders to a different locations

    Args:
        ns_path (StrOrPath): Namespace, where files should be moved.
        relocations (Iterable[RelocationPath]): Iterable, where each item contains
            current file path and path to move file to.

    Returns:
        list[FileTaskResult]: List, where each item contains either a moved file
            or an error code.
    """
    storage = _create_storage()

    results = []
    async with _create_database() as database:
        provider = Provider(database=database, storage=storage)
        services = provider.service

        for relocation in relocations:
            path, next_path = relocation.from_path, relocation.to_path
            file, err_code = None, None

            try:
                file = await services.namespace.move_file(ns_path, path, next_path)
            except errors.Error as exc:
                err_code = exc.code
            except Exception:
                err_code = errors.ErrorCode.internal
                logger.exception("Unexpectedly failed to move file")

            results.append(
                FileTaskResult(
                    file=file,  # type: ignore
                    err_code=err_code,
                )
            )
    return results


@asynctask
async def move_to_trash_batch(
    ns_path: StrOrPath,
    paths: Iterable[StrOrPath],
) -> list[FileTaskResult]:
    """
    Move several files to trash asynchronously.

    Args:
        ns_path (StrOrPath): Namespace, where files should be moved to trash
        paths (Iterable[StrOrPath]): Iterable of pathnames to move to trash.

    Returns:
        list[FileTaskResult]: List, where each item contains either a moved file
            or an error code.
    """
    storage = _create_storage()

    results = []
    async with _create_database() as database:
        provider = Provider(database=database, storage=storage)
        services = provider.service

        for path in paths:
            file, err_code = None, None

            try:
                file = await services.namespace.move_file_to_trash(ns_path, path)
            except errors.Error as exc:
                err_code = exc.code
            except Exception:
                err_code = errors.ErrorCode.internal
                logger.exception("Unexpectedly failed to move file to trash")

            results.append(
                FileTaskResult(
                    file=file,  # type: ignore
                    err_code=err_code,
                )
            )
    return results
