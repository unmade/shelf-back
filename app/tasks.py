from __future__ import annotations

import asyncio
import functools
import logging
from typing import TYPE_CHECKING

from celery import Celery
from pydantic import BaseModel

from app import config, errors
from app.app.files.domain import File
from app.infrastructure.database.edgedb.db import EdgeDBDatabase
from app.infrastructure.provider import Provider
from app.infrastructure.storage import FileSystemStorage, S3Storage

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.app.infrastructure import IStorage
    from app.typedefs import StrOrPath

logger = logging.getLogger(__name__)

celery_app = Celery(__name__)


class RelocationPath(BaseModel):
    from_path: str
    to_path: str


class FileTaskResult:
    __slots__ = ("file", "err_code")

    def __init__(
        self,
        file: File | None = None,
        err_code: errors.ErrorCode | None = None,
    ) -> None:
        self.file = file
        self.err_code = err_code


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
    ns_path: StrOrPath,
    paths: Iterable[StrOrPath],
) -> list[FileTaskResult]:
    """
    Permanently deletes a file at given paths. If some file is a folder, then it will be
    deleted with all of its contents.

    Args:
        ns_path (StrOrPath): Namespace path where file/folder should be deleted.
        paths (Iterable[StrOrPath]): Iterable of pathnames to delete.

    Returns:
        list[FileTaskResult]: List, where each item contains either a moved file
            or an error code.
    """
    storage = _create_storage()

    results = []
    async with _create_database() as database:
        provider = Provider(database=database, storage=storage)
        usecases = provider.usecases

        for path in paths:
            file, err_code = None, None

            try:
                file = await usecases.namespace.delete_item(ns_path, path)
            except File.NotFound as exc:
                err_code = errors.ErrorCode(exc.code)
            except Exception:
                err_code = errors.ErrorCode.internal
                logger.exception("Unexpectedly failed to delete a file")

            result = FileTaskResult(file=file,err_code=err_code)
            results.append(result)
    return results


@asynctask
async def empty_trash(ns_path: StrOrPath) -> None:
    """
    Deletes all files and folders in the Trash folder within a target Namespace.

    Args:
        namespace (Namespace): Namespace where Trash should be emptied.
    """
    storage = _create_storage()

    async with _create_database() as database:
        provider = Provider(database=database, storage=storage)
        usecases = provider.usecases
        try:
            await usecases.namespace.empty_trash(ns_path)
        except Exception:
            logger.exception("Unexpectedly failed to empty trash folder")


@asynctask
async def move_batch(
    ns_path: StrOrPath,
    relocations: Iterable[RelocationPath],
) -> list[FileTaskResult]:
    """
    Moves several files/folders to a different locations

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
        usecases = provider.usecases

        for relocation in relocations:
            path, next_path = relocation.from_path, relocation.to_path
            file, err_code = None, None

            try:
                file = await usecases.namespace.move_item(ns_path, path, next_path)
            except errors.Error as exc:
                err_code = exc.code
            except Exception:
                err_code = errors.ErrorCode.internal
                logger.exception("Unexpectedly failed to move file")

            result = FileTaskResult(file=file,err_code=err_code)
            results.append(result)
    return results


@asynctask
async def move_to_trash_batch(
    ns_path: StrOrPath,
    paths: Iterable[StrOrPath],
) -> list[FileTaskResult]:
    """
    Moves several files to trash asynchronously.

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
        usecases = provider.usecases

        for path in paths:
            file, err_code = None, None

            try:
                file = await usecases.namespace.move_item_to_trash(ns_path, path)
            except errors.Error as exc:
                err_code = exc.code
            except Exception:
                err_code = errors.ErrorCode.internal
                logger.exception("Unexpectedly failed to move file to trash")

            result = FileTaskResult(file=file,err_code=err_code)
            results.append(result)
    return results
