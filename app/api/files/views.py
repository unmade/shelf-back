from __future__ import annotations

from uuid import UUID

import celery.states
from fastapi import APIRouter, Depends, Form, Query, Request, UploadFile
from fastapi import File as FileParam
from fastapi.responses import ORJSONResponse, Response, StreamingResponse

from app import errors, tasks
from app.api import deps, shortcuts
from app.app.files.domain import ContentMetadata, File, Namespace, mediatypes
from app.infrastructure.provider import UseCases

from . import exceptions
from .schemas import (
    AsyncTaskID,
    AsyncTaskResult,
    AsyncTaskStatus,
    DeleteImmediatelyBatchCheckResponse,
    DeleteImmediatelyBatchRequest,
    EmptyTrashCheckResponse,
    FileSchema,
    FindDuplicatesRequest,
    FindDuplicatesResponse,
    GetBatchRequest,
    GetBatchResponse,
    GetContentMetadataResponse,
    GetDownloadUrlResponse,
    ListFolderResponse,
    MoveBatchCheckResponse,
    MoveBatchRequest,
    MoveToTrashBatchRequest,
    PathParam,
    PathRequest,
    ThumbnailSize,
)

router = APIRouter()


@router.post("/create_folder")
async def create_folder(
    request: Request,
    payload: PathRequest,
    namespace: Namespace = Depends(deps.namespace),
    usecases: UseCases = Depends(deps.usecases),
) -> FileSchema:
    """
    Create a new folder with a target path.

    Any missing parents of the folder path are created as needed.
    If a path provided in a format 'a/b/c', then 'a' and 'b' folders will be created,
    if not existed, and 'c' will be returned as a response.
    """
    try:
        folder = await usecases.namespace.create_folder(namespace.path, payload.path)
    except File.AlreadyExists as exc:
        raise exceptions.FileAlreadyExists(path=payload.path) from exc
    except File.NotADirectory as exc:
        raise exceptions.NotADirectory(path=payload.path) from exc

    return FileSchema.from_entity(folder, request=request)


@router.post("/delete_immediately_batch")
def delete_immediately_batch(
    payload: DeleteImmediatelyBatchRequest,
    namespace: Namespace = Depends(deps.namespace),
) -> AsyncTaskID:
    """Permanently delete multiple files or folders."""
    paths = [item.path for item in payload.items]
    task = tasks.delete_immediately_batch.delay(namespace.path, paths)
    return AsyncTaskID(async_task_id=task.id)


@router.post("/delete_immediately_batch/check")
def delete_immediately_check(
    request: Request,
    payload: AsyncTaskID,
    _: Namespace = Depends(deps.namespace),
) -> DeleteImmediatelyBatchCheckResponse:
    response_model = DeleteImmediatelyBatchCheckResponse
    task = tasks.celery_app.AsyncResult(str(payload.async_task_id))
    if task.status == celery.states.SUCCESS:
        return response_model(
            status=AsyncTaskStatus.completed,
            result=[
                AsyncTaskResult.from_entity(result, request=request)
                for result in task.result
            ],
        )
    return response_model(status=AsyncTaskStatus.pending)


@router.get("/download")
async def download(
    key: str = Query(None),
    usecases: UseCases = Depends(deps.usecases),
):
    """
    Download a file or a folder.

    This endpoint is useful to perform downloads with browser. A `key` is obtained by
    calling `get_download_url` endpoint. Folders will be downloaded as a ZIP archive.
    """
    value = await shortcuts.pop_download_cache(key)
    if not value:
        raise exceptions.DownloadNotFound()

    try:
        file, content = await usecases.namespace.download(value.ns_path, value.path)
    except File.NotFound as exc:
        raise exceptions.PathNotFound(path=value.path) from exc

    filename = file.name.encode("utf-8").decode("latin-1")
    if content.zipped:
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}.zip"',
            "Content-Type": "attachment/zip",
        }
    else:
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(file.size),
            "Content-Type": file.mediatype,
        }
    return StreamingResponse(content, headers=headers)


@router.post("/download")
async def download_xhr(
    payload: PathRequest,
    namespace: Namespace = Depends(deps.namespace),
    usecases: UseCases = Depends(deps.usecases),
):
    """
    Download a file or a folder.

    This endpoint is useful to download files with XHR. Folders will be downloaded as a
    ZIP archive."""
    try:
        file, content = await usecases.namespace.download(namespace.path, payload.path)
    except File.NotFound as exc:
        raise exceptions.PathNotFound(path=payload.path) from exc

    filename = file.name.encode("utf-8").decode("latin-1")
    if content.zipped:
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}.zip"',
            "Content-Type": "attachment/zip",
        }
    else:
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(file.size),
            "Content-Type": file.mediatype,
        }

    return StreamingResponse(content, headers=headers)


@router.post("/empty_trash")
def empty_trash(
    namespace: Namespace = Depends(deps.namespace),
) -> AsyncTaskID:
    """Delete all files and folders in the Trash folder."""
    task = tasks.empty_trash.delay(namespace.path)
    return AsyncTaskID(async_task_id=task.id)


@router.post("/empty_trash/check")
def empty_trash_check(
    payload: AsyncTaskID,
    _: Namespace = Depends(deps.namespace),
) -> EmptyTrashCheckResponse:
    """Return empty_trash status."""
    response_model = EmptyTrashCheckResponse
    task = tasks.celery_app.AsyncResult(str(payload.async_task_id))
    if task.status == celery.states.SUCCESS:
        return response_model(status=AsyncTaskStatus.completed)
    return response_model(status=AsyncTaskStatus.pending)


@router.post("/find_duplicates", response_model=FindDuplicatesResponse)
async def find_duplicates(
    request: Request,
    payload: FindDuplicatesRequest,
    namespace: Namespace = Depends(deps.namespace),
    usecases: UseCases = Depends(deps.usecases),
):
    """Find all duplicate files in a folder including all sub-folders."""
    ns_path = namespace.path
    path, max_distance = payload.path, payload.max_distance

    groups = await usecases.namespace.find_duplicates(ns_path, path, max_distance)

    # by returning response class directly we avoid pydantic checks
    # that way we speed up on a large volume of data
    return ORJSONResponse(content={
        "path": payload.path,
        "items": [
            [
                FileSchema.from_entity(file, request=request).dict()
                for file in group
            ]
            for group in groups
        ],
        "count": len(groups),
    })


@router.post("/get_batch", response_model=GetBatchResponse, deprecated=True)
async def get_batch(
    request: Request,
    payload: GetBatchRequest,
    namespace: Namespace = Depends(deps.namespace),
    usecases: UseCases = Depends(deps.usecases),
):
    """Return all files with specified IDs."""
    ns_path = namespace.path
    files = await usecases.namespace.filecore.get_by_id_batch(ns_path, payload.ids)

    # by returning response class directly we avoid pydantic checks
    # that way we speed up on a large volume of data
    return ORJSONResponse(content={
        "items": [
            FileSchema.from_entity(file, request=request).dict()
            for file in files
        ],
        "count": len(files),
    })


@router.post("/get_download_url")
async def get_download_url(
    request: Request,
    payload: PathRequest,
    namespace: Namespace = Depends(deps.namespace),
    usecases: UseCases = Depends(deps.usecases),
) -> GetDownloadUrlResponse:
    """Return a link to download requested file or folder."""
    try:
        file = await usecases.namespace.get_item_at_path(namespace.path, payload.path)
    except File.NotFound as exc:
        raise exceptions.PathNotFound(path=payload.path) from exc

    key = await shortcuts.create_download_cache(namespace.path, file.path)

    download_url = request.url_for("download")
    return GetDownloadUrlResponse(download_url=f"{download_url}?key={key}")


@router.post("/get_content_metadata")
async def get_content_metadata(
    payload: PathRequest,
    usecases: UseCases = Depends(deps.usecases),
    namespace: Namespace = Depends(deps.namespace),
) -> GetContentMetadataResponse:
    """Return content metadata for a given file."""
    try:
        meta = await usecases.namespace.get_file_metadata(namespace.path, payload.path)
    except File.NotFound as exc:
        raise exceptions.PathNotFound(path=payload.path) from exc
    except ContentMetadata.NotFound as exc:
        raise exceptions.FileContentMetadataNotFound(path=payload.path) from exc
    return GetContentMetadataResponse.from_entity(meta)


@router.get("/get_thumbnail/{file_id}")
async def get_thumbnail(
    file_id: UUID,
    size: ThumbnailSize,
    usecases: UseCases = Depends(deps.usecases),
    namespace: Namespace = Depends(deps.namespace),
):
    """Get thumbnail for an image file."""
    try:
        file, thumbnail = await usecases.namespace.get_file_thumbnail(
            namespace.path, str(file_id), size=size.asint()
        )
    except File.NotFound as exc:
        raise exceptions.PathNotFound(path=str(file_id)) from exc
    except File.IsADirectory as exc:
        raise exceptions.IsADirectory(path=str(file_id)) from exc
    except errors.ThumbnailUnavailable as exc:
        raise exceptions.ThumbnailUnavailable(path=str(file_id)) from exc

    filename = file.name.encode("utf-8").decode("latin-1")

    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "Content-Length": str(len(thumbnail)),
        "Content-Type": mediatypes.IMAGE_WEBP,
        "Cache-Control": "private, max-age=31536000, no-transform",
    }

    return Response(thumbnail, headers=headers)


@router.post("/list_folder", response_model=ListFolderResponse)
async def list_folder(
    request: Request,
    payload: PathRequest,
    namespace: Namespace = Depends(deps.namespace),
    usecases: UseCases = Depends(deps.usecases),
):
    """
    List content of a folder with a given path.

    Note, that Trash folder is never present in a result.
    """
    try:
        files = await usecases.namespace.list_folder(namespace.path, payload.path)
    except File.NotFound as exc:
        raise exceptions.PathNotFound(path=payload.path) from exc
    except File.NotADirectory as exc:
        raise exceptions.NotADirectory(path=payload.path) from exc

    # by returning response class directly we avoid pydantic checks
    # that way we speed up on a large volume of data
    return ORJSONResponse(content={
        "path": payload.path,
        "items": [
            FileSchema.from_entity(file, request=request).dict()
            for file in files
        ],
        "count": len(files),
    })


@router.post("/move_batch")
def move_batch(
    payload: MoveBatchRequest,
    namespace: Namespace = Depends(deps.namespace),
) -> AsyncTaskID:
    """Move multiple files or folders to different locations at once."""
    task = tasks.move_batch.delay(namespace.path, payload.items)
    return AsyncTaskID(async_task_id=task.id)


@router.post("/move_batch/check")
def move_batch_check(
    request: Request,
    payload: AsyncTaskID,
    _: Namespace = Depends(deps.namespace),
) -> MoveBatchCheckResponse:
    """Return move_batch status and a list of results."""
    response_model = MoveBatchCheckResponse
    task = tasks.celery_app.AsyncResult(str(payload.async_task_id))
    if task.status == celery.states.SUCCESS:
        return response_model(
            status=AsyncTaskStatus.completed,
            result=[
                AsyncTaskResult.from_entity(result, request=request)
                for result in task.result
            ],
        )
    return response_model(status=AsyncTaskStatus.pending)


@router.post("/move_to_trash_batch")
def move_to_trash_batch(
    payload: MoveToTrashBatchRequest,
    namespace: Namespace = Depends(deps.namespace),
) -> AsyncTaskID:
    """
    Move several files or folders to Trash at once.

    To check task result use the same endpoint to check regular move result.
    """
    paths = [item.path for item in payload.items]
    task = tasks.move_to_trash_batch.delay(namespace.path, paths)
    return AsyncTaskID(async_task_id=task.id)


@router.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = FileParam(...),
    path: PathParam = Form(...),
    namespace: Namespace = Depends(deps.namespace),
    usecases: UseCases = Depends(deps.usecases),
) -> FileSchema:
    """Upload file to the specified path."""
    filepath = path.__root__
    del path

    ns_path = str(namespace.path)
    try:
        upload = await usecases.namespace.add_file(ns_path, filepath, file.file)
    except File.TooLarge as exc:
        raise exceptions.UploadFileTooLarge() from exc
    except File.MalformedPath as exc:
        raise exceptions.MalformedPath(str(exc)) from exc
    except File.NotADirectory as exc:
        raise exceptions.NotADirectory(path=filepath) from exc
    except errors.StorageQuotaExceeded as exc:
        raise exceptions.StorageQuotaExceeded() from exc

    return FileSchema.from_entity(upload, request=request)
