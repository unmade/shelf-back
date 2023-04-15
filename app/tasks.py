from __future__ import annotations

import asyncio
import enum
import functools
import logging
from typing import TYPE_CHECKING

from celery import Celery
from pydantic import BaseModel

from app.app.files.domain import File
from app.config import config
from app.infrastructure.context import AppContext

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.app.audit.domain import CurrentUserContext
    from app.app.files.domain import AnyPath

logger = logging.getLogger(__name__)

celery_app = Celery(__name__)


class RelocationPath(BaseModel):
    from_path: str
    to_path: str


class ErrorCode(str, enum.Enum):
    internal = "internal_error"
    file_already_exists = "file_already_exists"
    file_not_found = "file_not_found"
    file_too_large = "file_too_large"
    is_a_directory = "is_a_directory"
    malformed_path = "malformed_path"
    missing_parent = "missing_parent"
    not_a_directory = "not_a_directory"


class FileTaskResult:
    __slots__ = ("file", "err_code")

    def __init__(
        self,
        file: File | None = None,
        err_code: ErrorCode | None = None,
    ) -> None:
        self.file = file
        self.err_code = err_code


def exc_to_err_code(exc: Exception) -> ErrorCode:
    err_map: dict[type[Exception], ErrorCode] = {
        File.AlreadyExists: ErrorCode.file_already_exists,
        File.NotFound: ErrorCode.file_not_found,
        File.TooLarge: ErrorCode.file_too_large,
        File.IsADirectory: ErrorCode.is_a_directory,
        File.MalformedPath: ErrorCode.malformed_path,
        File.MissingParent: ErrorCode.missing_parent,
        File.NotADirectory: ErrorCode.not_a_directory,
    }
    if code := err_map.get(exc.__class__):
        return code
    return ErrorCode.internal


class CeleryConfig:
    broker_url = config.celery.broker_dsn
    result_backend = config.celery.backend_dsn
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
    ns_path: AnyPath,
    paths: Iterable[AnyPath],
) -> list[FileTaskResult]:
    """
    Permanently deletes a file at given paths. If some file is a folder, then it will be
    deleted with all of its contents.

    Args:
        ns_path (AnyPath): Namespace path where file/folder should be deleted.
        paths (Iterable[AnyPath]): Iterable of pathnames to delete.

    Returns:
        list[FileTaskResult]: List, where each item contains either a moved file
            or an error code.
    """

    results = []
    async with AppContext(config.database, config.storage) as ctx:
        for path in paths:
            file, err_code = None, None

            try:
                file = await ctx.usecases.namespace.delete_item(ns_path, path)
            except Exception as exc:
                err_code = exc_to_err_code(exc)
                if err_code == ErrorCode.internal:
                    logger.exception("Unexpectedly failed to delete a file")

            result = FileTaskResult(file=file,err_code=err_code)
            results.append(result)
    return results


@asynctask
async def empty_trash(
    ns_path: AnyPath,
    *,
    context: CurrentUserContext,
) -> None:
    """
    Deletes all files and folders in the Trash folder within a target Namespace.

    Args:
        namespace (Namespace): Namespace where Trash should be emptied.
    """
    async with AppContext(config.database, config.storage) as ctx:
        with context:
            try:
                await ctx.usecases.namespace.empty_trash(ns_path)
            except Exception:
                logger.exception("Unexpectedly failed to empty trash folder")


@asynctask
async def move_batch(
    ns_path: AnyPath,
    relocations: Iterable[RelocationPath],
    *,
    context: CurrentUserContext,
) -> list[FileTaskResult]:
    """
    Moves several files/folders to a different locations

    Args:
        ns_path (AnyPath): Namespace, where files should be moved.
        relocations (Iterable[RelocationPath]): Iterable, where each item contains
            current file path and path to move file to.

    Returns:
        list[FileTaskResult]: List, where each item contains either a moved file
            or an error code.
    """
    results = []
    async with AppContext(config.database, config.storage) as ctx:
        move_item = ctx.usecases.namespace.move_item
        with context:
            for relocation in relocations:
                path, next_path = relocation.from_path, relocation.to_path
                file, err_code = None, None

                try:
                    file = await move_item(ns_path, path, next_path)
                except Exception as exc:
                    err_code = exc_to_err_code(exc)
                    if err_code == ErrorCode.internal:
                        logger.exception("Unexpectedly failed to move a file")

                result = FileTaskResult(file=file,err_code=err_code)
                results.append(result)
            return results


@asynctask
async def move_to_trash_batch(
    ns_path: AnyPath,
    paths: Iterable[AnyPath],
    *,
    context: CurrentUserContext,
) -> list[FileTaskResult]:
    """
    Moves several files to trash asynchronously.

    Args:
        ns_path (AnyPath): Namespace, where files should be moved to trash
        paths (Iterable[AnyPath]): Iterable of pathnames to move to trash.

    Returns:
        list[FileTaskResult]: List, where each item contains either a moved file
            or an error code.
    """
    results = []
    async with AppContext(config.database, config.storage) as ctx:
        move_item_to_trash = ctx.usecases.namespace.move_item_to_trash
        with context:
            for path in paths:
                file, err_code = None, None

                try:
                    file = await move_item_to_trash(ns_path, path)
                except Exception as exc:
                    err_code = exc_to_err_code(exc)
                    if err_code == ErrorCode.internal:
                        logger.exception("Unexpectedly failed to move file to trash")

                result = FileTaskResult(file=file,err_code=err_code)
                results.append(result)
            return results
