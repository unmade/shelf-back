from __future__ import annotations

import enum
import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.app.files.domain import File

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from uuid import UUID

    from app.app.audit.domain import CurrentUserContext
    from app.app.files.domain import AnyFile, AnyPath

    from ..main import ARQContext

logger = logging.getLogger(__name__)


class RelocationPath(BaseModel):
    from_path: str
    to_path: str


class ErrorCode(str, enum.Enum):
    internal = "internal_error"
    file_action_not_allowed = "file_action_not_allowed"
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
        file: AnyFile | None = None,
        err_code: ErrorCode | None = None,
    ) -> None:
        self.file = file
        self.err_code = err_code


def exc_to_err_code(exc: Exception) -> ErrorCode:
    err_map: dict[type[Exception], ErrorCode] = {
        File.ActionNotAllowed: ErrorCode.file_action_not_allowed,
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


async def delete_immediately_batch(
    ctx: ARQContext,
    ns_path: AnyPath,
    paths: Iterable[AnyPath],
) -> list[FileTaskResult]:
    """
    Permanently deletes a file at given paths. If some file is a folder, then it will be
    deleted with all of its contents.
    """

    results = []
    for path in paths:
        file, err_code = None, None

        try:
            file = await ctx["usecases"].namespace.delete_item(ns_path, path)
        except Exception as exc:
            err_code = exc_to_err_code(exc)
            if err_code == ErrorCode.internal:
                logger.exception("Unexpectedly failed to delete a file")

        result = FileTaskResult(file=file, err_code=err_code)
        results.append(result)
    return results


async def empty_trash(
    ctx: ARQContext,
    ns_path: AnyPath,
    *,
    context: CurrentUserContext,
) -> None:
    """Deletes all files and folders in the Trash folder within a target Namespace."""
    with context:
        try:
            await ctx["usecases"].namespace.empty_trash(ns_path)
        except Exception:
            logger.exception("Unexpectedly failed to empty trash folder")


async def move_batch(
    ctx: ARQContext,
    ns_path: AnyPath,
    relocations: Iterable[RelocationPath],
    *,
    context: CurrentUserContext,
) -> list[FileTaskResult]:
    """Moves several files/folders to a different locations."""
    results = []
    move_item = ctx["usecases"].namespace.move_item
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

            result = FileTaskResult(file=file, err_code=err_code)
            results.append(result)
    return results


async def move_to_trash_batch(
    ctx: ARQContext,
    ns_path: AnyPath,
    paths: Iterable[AnyPath],
    *,
    context: CurrentUserContext,
) -> list[FileTaskResult]:
    """Moves several files to trash asynchronously."""
    results = []
    move_item_to_trash = ctx["usecases"].namespace.move_item_to_trash
    with context:
        for path in paths:
            file, err_code = None, None

            try:
                file = await move_item_to_trash(ns_path, path)
            except Exception as exc:
                err_code = exc_to_err_code(exc)
                if err_code == ErrorCode.internal:
                    logger.exception("Unexpectedly failed to move file to trash")

            result = FileTaskResult(file=file, err_code=err_code)
            results.append(result)
    return results


async def process_file_content(ctx: ARQContext, file_id: UUID) -> None:
    content_service = ctx["usecases"].namespace.content
    await content_service.process(file_id)


async def process_file_pending_deletion(ctx: ARQContext, ids: Sequence[UUID]) -> None:
    filecore = ctx["usecases"].namespace.file.filecore
    thumbnailer = ctx["usecases"].namespace.thumbnailer
    result = await filecore.process_file_pending_deletion(ids)
    chashes = [
        item.chash
        for item in result
        if item.chash and thumbnailer.is_supported(item.mediatype)
    ]
    await thumbnailer.delete_stale_thumbnails(chashes)
