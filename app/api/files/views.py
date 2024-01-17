from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Form, Request
from fastapi import File as FileParam
from fastapi.responses import Response, StreamingResponse

from app.api import shortcuts
from app.api.deps import (
    CurrentUserContextDeps,
    DownloadCacheDeps,
    NamespaceDeps,
    UseCasesDeps,
    WorkerDeps,
)
from app.app.files.domain import ContentMetadata, File, mediatypes
from app.app.infrastructure.worker import JobStatus
from app.app.users.domain import Account

from . import exceptions
from .schemas import (
    AsyncTaskID,
    AsyncTaskResult,
    AsyncTaskStatus,
    CreateFolderRequest,
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
    IDRequest,
    ListFolderResponse,
    MoveBatchCheckResponse,
    MoveBatchRequest,
    MoveToTrashBatchRequest,
    PathParam,
    PathRequest,
    ThumbnailSize,
    UploadContent,
)

router = APIRouter()


@router.post("/create_folder")
async def create_folder(
    request: Request,
    payload: CreateFolderRequest,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
) -> FileSchema:
    """
    Create a new folder with a target path.

    Any missing parents of the folder path are created as needed.
    If a path provided in a format 'a/b/c', then 'a' and 'b' folders will be created,
    if not existed, and 'c' will be returned as a response.
    """
    try:
        folder = await usecases.namespace.create_folder(namespace.path, payload.path)
    except File.ActionNotAllowed as exc:
        raise exceptions.FileActionNotAllowed() from exc
    except File.AlreadyExists as exc:
        raise exceptions.FileAlreadyExists(path=payload.path) from exc
    except File.NotADirectory as exc:
        raise exceptions.NotADirectory(path=payload.path) from exc

    return FileSchema.from_entity(folder, request=request)


@router.post("/delete_immediately_batch")
async def delete_immediately_batch(
    payload: DeleteImmediatelyBatchRequest,
    namespace: NamespaceDeps,
    worker: WorkerDeps,
) -> AsyncTaskID:
    """Permanently delete multiple files or folders."""
    paths = [item.path for item in payload.items]
    job = await worker.enqueue("delete_immediately_batch", namespace.path, paths)
    return AsyncTaskID(async_task_id=job.id)


@router.post("/delete_immediately_batch/check")
async def delete_immediately_check(
    request: Request,
    payload: AsyncTaskID,
    _: NamespaceDeps,
    worker: WorkerDeps,
) -> DeleteImmediatelyBatchCheckResponse:
    response_model = DeleteImmediatelyBatchCheckResponse
    status = await worker.get_status(payload.async_task_id)
    if status == JobStatus.complete:
        result = await worker.get_result(payload.async_task_id)
        return response_model(
            status=AsyncTaskStatus.completed,
            result=[
                AsyncTaskResult.from_entity(result, request=request)
                for result in result
            ]
        )
    return response_model(status=AsyncTaskStatus.pending)


@router.get("/download")
async def download(
    usecases: UseCasesDeps,
    file: DownloadCacheDeps,
):
    """
    Download a file.

    A `key` is obtained by calling `get_download_url` endpoint.
    """
    try:
        content = await usecases.namespace.download_by_id(file.id)
    except File.IsADirectory as exc:
        raise exceptions.IsADirectory(path=file.path) from exc
    except File.NotFound as exc:
        raise exceptions.PathNotFound(path=file.path) from exc

    filename = file.path.name.encode("utf-8").decode("latin-1")
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Length": str(file.size),
        "Content-Type": file.mediatype,
    }
    return StreamingResponse(content, headers=headers)


@router.post("/download")
async def download_xhr(
    payload: PathRequest,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
):
    """
    Download a file.

    This endpoint is useful to download files with XHR.
    """
    try:
        file, content = await usecases.namespace.download(namespace.path, payload.path)
    except File.ActionNotAllowed as exc:
        raise exceptions.FileActionNotAllowed() from exc
    except File.IsADirectory as exc:
        raise exceptions.IsADirectory(path=payload.path) from exc
    except File.NotFound as exc:
        raise exceptions.PathNotFound(path=payload.path) from exc

    filename = file.name.encode("utf-8").decode("latin-1")
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Length": str(file.size),
        "Content-Type": file.mediatype,
    }

    return StreamingResponse(content, headers=headers)


@router.get("/download_folder")
def download_folder(
    usecases: UseCasesDeps,
    file: DownloadCacheDeps,
):
    """
    Download a folder as a ZIP archive.

    A `key` is obtained by calling `get_download_url` endpoint.
    """
    content = usecases.namespace.download_folder(file.ns_path, file.path)

    filename = file.name.encode("utf-8").decode("latin-1")
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}.zip"',
        "Content-Type": "attachment/zip",
    }
    return StreamingResponse(content, headers=headers)


@router.post("/empty_trash")
async def empty_trash(
    namespace: NamespaceDeps,
    current_user_ctx: CurrentUserContextDeps,
    worker: WorkerDeps,
) -> AsyncTaskID:
    """Delete all files and folders in the Trash folder."""
    job = await worker.enqueue("empty_trash", namespace.path, context=current_user_ctx)
    return AsyncTaskID(async_task_id=job.id)


@router.post("/empty_trash/check")
async def empty_trash_check(
    payload: AsyncTaskID,
    _: NamespaceDeps,
    worker: WorkerDeps,
) -> EmptyTrashCheckResponse:
    """Return empty_trash status."""
    response_model = EmptyTrashCheckResponse
    status = await worker.get_status(payload.async_task_id)
    if status == JobStatus.complete:
        await worker.get_result(payload.async_task_id)
        return response_model(status=AsyncTaskStatus.completed)
    return response_model(status=AsyncTaskStatus.pending)


@router.post("/find_duplicates")
async def find_duplicates(
    request: Request,
    payload: FindDuplicatesRequest,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
) -> FindDuplicatesResponse:
    """Find all duplicate files in a folder including all sub-folders."""
    ns_path = namespace.path
    path, max_distance = payload.path, payload.max_distance

    groups = await usecases.namespace.find_duplicates(ns_path, path, max_distance)

    return FindDuplicatesResponse(
        path=payload.path,
        items=[
            [
                FileSchema.from_entity(file, request=request)
                for file in group
            ]
            for group in groups
        ],
        count=len(groups),
    )


@router.post("/get_batch")
async def get_batch(
    request: Request,
    payload: GetBatchRequest,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
) -> GetBatchResponse:
    """Return all files with specified IDs."""
    ns_path = namespace.path
    files = await usecases.namespace.file.get_by_id_batch(ns_path, payload.ids)

    return GetBatchResponse(
        items=[FileSchema.from_entity(file, request=request) for file in files],
        count=len(files),
    )


@router.post("/get_download_url")
async def get_download_url(
    request: Request,
    payload: PathRequest,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
) -> GetDownloadUrlResponse:
    """Return a link to download requested file or folder."""
    try:
        file = await usecases.namespace.get_item_at_path(namespace.path, payload.path)
    except File.ActionNotAllowed as exc:
        raise exceptions.FileActionNotAllowed() from exc
    except File.NotFound as exc:
        raise exceptions.PathNotFound(path=payload.path) from exc

    if not file.can_download():
        raise exceptions.FileActionNotAllowed() from None

    key = await shortcuts.create_download_cache(file)
    if file.is_folder():
        download_url = request.url_for("download_folder")
    else:
        download_url = request.url_for("download")
    return GetDownloadUrlResponse(download_url=f"{download_url}?key={key}")


@router.post("/get_content_metadata")
async def get_content_metadata(
    payload: IDRequest,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
) -> GetContentMetadataResponse:
    """Return content metadata for a given file."""
    try:
        meta = await usecases.namespace.get_file_metadata(namespace.path, payload.id)
    except File.ActionNotAllowed as exc:
        raise exceptions.FileActionNotAllowed() from exc
    except File.NotFound as exc:
        raise exceptions.PathNotFound(path=str(payload.id)) from exc
    except ContentMetadata.NotFound as exc:
        raise exceptions.FileContentMetadataNotFound(path=str(payload.id)) from exc
    return GetContentMetadataResponse.from_entity(meta)


@router.get("/get_thumbnail/{file_id}")
async def get_thumbnail(
    file_id: UUID,
    size: ThumbnailSize,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
):
    """Get thumbnail for an image file."""
    try:
        file, thumbnail = await usecases.namespace.get_file_thumbnail(
            namespace.path, file_id, size=size.asint()
        )
    except File.ActionNotAllowed as exc:
        raise exceptions.FileActionNotAllowed() from exc
    except File.NotFound as exc:
        raise exceptions.PathNotFound(path=str(file_id)) from exc
    except File.IsADirectory as exc:
        raise exceptions.IsADirectory(path=str(file_id)) from exc
    except File.ThumbnailUnavailable as exc:
        raise exceptions.ThumbnailUnavailable(path=str(file_id)) from exc

    filename = file.name.encode("utf-8").decode("latin-1")

    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "Content-Length": str(len(thumbnail)),
        "Content-Type": mediatypes.IMAGE_WEBP,
        "Cache-Control": "private, max-age=31536000, no-transform",
    }

    return Response(thumbnail, headers=headers)


@router.post("/list_folder")
async def list_folder(
    request: Request,
    payload: PathRequest,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
) -> ListFolderResponse:
    """
    List content of a folder with a given path.

    Note, that Trash folder is never present in a result.
    """
    try:
        files = await usecases.namespace.list_folder(namespace.path, payload.path)
    except File.ActionNotAllowed as exc:
        raise exceptions.FileActionNotAllowed() from exc
    except File.NotFound as exc:
        raise exceptions.PathNotFound(path=payload.path) from exc
    except File.NotADirectory as exc:
        raise exceptions.NotADirectory(path=payload.path) from exc

    return ListFolderResponse(
        path=payload.path,
        items=[FileSchema.from_entity(file, request=request) for file in files],
        count=len(files),
    )


@router.post("/move_batch")
async def move_batch(
    payload: MoveBatchRequest,
    namespace: NamespaceDeps,
    current_user_ctx: CurrentUserContextDeps,
    worker: WorkerDeps,
) -> AsyncTaskID:
    """Move multiple files or folders to different locations at once."""
    job = await worker.enqueue(
        "move_batch", namespace.path, payload.items, context=current_user_ctx
    )
    return AsyncTaskID(async_task_id=job.id)


@router.post("/move_batch/check")
async def move_batch_check(
    request: Request,
    payload: AsyncTaskID,
    _: NamespaceDeps,
    worker: WorkerDeps,
) -> MoveBatchCheckResponse:
    """Return move_batch status and a list of results."""
    response_model = MoveBatchCheckResponse
    status = await worker.get_status(payload.async_task_id)
    if status == JobStatus.complete:
        result = await worker.get_result(payload.async_task_id)
        return response_model(
            status=AsyncTaskStatus.completed,
            result=[
                AsyncTaskResult.from_entity(result, request=request)
                for result in result
            ]
        )
    return response_model(status=AsyncTaskStatus.pending)


@router.post("/move_to_trash_batch")
async def move_to_trash_batch(
    payload: MoveToTrashBatchRequest,
    namespace: NamespaceDeps,
    current_user_ctx: CurrentUserContextDeps,
    worker: WorkerDeps,
) -> AsyncTaskID:
    """
    Move several files or folders to Trash at once.

    To check task result use the same endpoint to check regular move result.
    """
    paths = [item.path for item in payload.items]
    job = await worker.enqueue(
        "move_to_trash_batch", namespace.path, paths, context=current_user_ctx
    )
    return AsyncTaskID(async_task_id=job.id)


@router.post("/upload")
async def upload_file(
    request: Request,
    namespace: NamespaceDeps,
    usecases: UseCasesDeps,
    file: UploadContent = FileParam(...),
    path: PathParam = Form(...),
) -> FileSchema:
    """Upload file to the specified path."""
    filepath = str(path.root)
    del path

    ns_path = str(namespace.path)
    try:
        upload = await usecases.namespace.add_file(ns_path, filepath, file)
    except File.ActionNotAllowed as exc:
        raise exceptions.FileActionNotAllowed() from exc
    except Account.StorageQuotaExceeded as exc:
        raise exceptions.StorageQuotaExceeded() from exc
    except File.MalformedPath as exc:
        raise exceptions.MalformedPath(str(exc)) from exc
    except File.NotADirectory as exc:
        raise exceptions.NotADirectory(path=filepath) from exc
    except File.TooLarge as exc:
        raise exceptions.UploadFileTooLarge() from exc

    return FileSchema.from_entity(upload, request=request)
