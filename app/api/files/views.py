from __future__ import annotations

import secrets
from io import BytesIO
from pathlib import Path

import celery.states
from cashews import cache
from edgedb import AsyncIOPool
from fastapi import APIRouter, Depends
from fastapi import File as FileParam
from fastapi import Form, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse

from app import actions, config, crud, errors, tasks
from app.api import deps
from app.entities import Namespace, User
from app.storage import storage

from . import exceptions, schemas

router = APIRouter()


@router.post("/create_folder", response_model=schemas.File)
async def create_folder(
    payload: schemas.PathRequest,
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    namespace: Namespace = Depends(deps.namespace),
):
    """
    Create a new folder with a target path.

    Any missing parents of the folder path are created as needed.
    If a path provided in a format 'a/b/c', then 'a' and 'b' folders will be created,
    if not existed, and 'c' will be returned as a response.
    """
    try:
        return await actions.create_folder(db_pool, namespace, payload.path)
    except errors.FileAlreadyExists as exc:
        raise exceptions.FileAlreadyExists(path=payload.path) from exc
    except errors.NotADirectory as exc:
        raise exceptions.NotADirectory(path=payload.path) from exc


@router.post("/delete_immediately", response_model=schemas.File)
async def delete_immediately(
    payload: schemas.DeletePathRequest,
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    namespace: Namespace = Depends(deps.namespace),
):
    """Permanently delete file or folder with its contents."""
    try:
        return await actions.delete_immediately(db_pool, namespace, payload.path)
    except errors.FileNotFound as exc:
        raise exceptions.PathNotFound(path=payload.path) from exc


@router.get("/download")
async def download(
    key: str = Query(None), db_pool: AsyncIOPool = Depends(deps.db_pool),
):
    """
    Download a file or a folder.

    This endpoint is useful to perform downloads with browser. A `key` is obtained by
    calling `get_download_url` endpoint. Folders will be downloaded as a ZIP archive.
    """
    value: str = await cache.get(key)
    if not value:
        raise exceptions.DownloadNotFound()
    await cache.delete(key)

    namespace, path = value.split(':', maxsplit=1)
    try:
        file = await crud.file.get(db_pool, namespace, path)
    except errors.FileNotFound as exc:
        raise exceptions.PathNotFound(path=path) from exc

    filename = file.name.encode("utf-8").decode("latin-1")
    if file.is_folder():
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
    fullpath = Path(namespace) / path
    return StreamingResponse(storage.download(fullpath), headers=headers)


@router.post("/download")
async def download_xhr(
    payload: schemas.PathRequest,
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    namespace: Namespace = Depends(deps.namespace),
):
    """
    Download a file or a folder.

    This endpoint is useful to download files with XHR. Folders will be downloaded as a
    ZIP archive."""
    try:
        file = await crud.file.get(db_pool, namespace.path, payload.path)
    except errors.FileNotFound as exc:
        raise exceptions.PathNotFound(path=payload.path) from exc

    filename = file.name.encode("utf-8").decode("latin-1")
    if file.is_folder():
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

    attachment = storage.download(namespace.path / payload.path)
    if file.is_folder() or file.size > config.APP_MAX_DOWNLOAD_WITHOUT_STREAMING:
        return StreamingResponse(attachment, headers=headers)

    buffer = BytesIO()
    for chunk in attachment:
        buffer.write(chunk)
    buffer.seek(0)

    return Response(buffer.read(), headers=headers)


@router.post("/empty_trash", response_model=schemas.File)
async def empty_trash(
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    namespace: Namespace = Depends(deps.namespace),
):
    """Delete all files and folders in the Trash folder."""
    return await actions.empty_trash(db_pool, namespace)


@router.post("/get_download_url", response_model=schemas.GetDownloadUrlResult)
async def get_download_url(
    request: Request,
    payload: schemas.PathRequest,
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    namespace: Namespace = Depends(deps.namespace),
):
    """Return a link to download requested file or folder."""
    try:
        file = await crud.file.get(db_pool, namespace.path, payload.path)
    except errors.FileNotFound as exc:
        raise exceptions.PathNotFound(path=payload.path) from exc

    key = secrets.token_urlsafe()
    await cache.set(key=key, value=f"{namespace.path}:{file.path}", expire=60)

    return {"download_url": f"{request.base_url}files/download?key={key}"}


@router.post("/get_thumbnail")
async def get_thumbnail(
    payload: schemas.PathRequest,
    size: schemas.ThumbnailSize = schemas.ThumbnailSize.xs,
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    namespace: Namespace = Depends(deps.namespace),
):
    """Generate thumbnail for an image file."""
    namespace = namespace
    path = payload.path

    try:
        file, disksize, thumbnail = (
            await actions.get_thumbnail(db_pool, namespace, path, size=size.asint())
        )
    except errors.FileNotFound as exc:
        raise exceptions.PathNotFound(path=path) from exc
    except errors.IsADirectory as exc:
        raise exceptions.IsADirectory(path=path) from exc
    except errors.ThumbnailUnavailable as exc:
        raise exceptions.ThumbnailUnavailable(path=path) from exc

    filename = file.name.encode("utf-8").decode("latin-1")
    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "Content-Length": str(disksize),
        "Content-Type": file.mediatype,
    }
    return StreamingResponse(thumbnail, headers=headers, media_type=file.mediatype)


@router.post("/list_folder", response_model=schemas.ListFolderResult)
async def list_folder(
    payload: schemas.PathRequest,
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    namespace: Namespace = Depends(deps.namespace),
):
    """
    List content of a folder with a given path.

    Note, that Trash folder is never present in a result.
    """
    try:
        files = await crud.file.list_folder(db_pool, namespace.path, payload.path)
    except errors.FileNotFound as exc:
        raise exceptions.PathNotFound(path=payload.path) from exc
    except errors.NotADirectory as exc:
        raise exceptions.NotADirectory(path=payload.path) from exc

    return schemas.ListFolderResult.construct(
        path=payload.path,
        items=[schemas.File.from_file(f) for f in files],
        count=len(files)
    )


@router.post("/move", response_model=schemas.File)
async def move(
    payload: schemas.MoveRequest,
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    namespace: Namespace = Depends(deps.namespace),
):
    """
    Move a file or folder to a different location in the target Namespace.
    If the source path is a folder all its contents will be moved.

    The last part of a new path would become new file/folder name.
    For example, to rename file with path 'file.txt', the new path should be
    'renamed_file.txt'.

    Note, this method doesn't allow to move file/folder to/from Trash folder.
    """
    from_path, to_path = payload.from_path, payload.to_path
    try:
        return await actions.move(db_pool, namespace, from_path, to_path)
    except errors.FileAlreadyExists as exc:
        raise exceptions.FileAlreadyExists(path=to_path) from exc
    except errors.FileNotFound as exc:
        raise exceptions.PathNotFound(path=from_path) from exc
    except errors.NotADirectory as exc:
        raise exceptions.NotADirectory(path=to_path) from exc
    except errors.MissingParent as exc:
        message = "Some parents don't exist in the destination path"
        raise exceptions.MalformedPath(message) from exc


@router.post("/move_batch", response_model=schemas.AsyncTaskID)
def move_batch(
    payload: schemas.MoveBatchRequest,
    namespace: Namespace = Depends(deps.namespace),
):
    """Move multiple files or folders to different locations at once."""
    task = tasks.move_batch.delay(namespace, payload.items)
    return schemas.AsyncTaskID(async_task_id=task.id)


@router.post("/move_batch/check", response_model=schemas.MoveBatchCheckResponse)
def move_batch_check(
    payload: schemas.AsyncTaskID,
    _: User = Depends(deps.current_user),
):
    """Return move_batch status and a list of results."""
    task = tasks.celery_app.AsyncResult(str(payload.async_task_id))
    if task.status == celery.states.SUCCESS:
        return schemas.MoveBatchCheckResponse(
            status=schemas.AsyncTaskStatus.completed,
            results=[
                schemas.MoveBatchResult(file=result.file, err_code=result.err_code)
                for result in task.result
            ]
        )
    return schemas.MoveBatchCheckResponse(status=schemas.AsyncTaskStatus.pending)


@router.post("/move_to_trash", response_model=schemas.File)
async def move_to_trash(
    payload: schemas.MoveToTrashRequest,
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    namespace: Namespace = Depends(deps.namespace),
):
    """Move file to the Trash folder."""
    try:
        return await actions.move_to_trash(db_pool, namespace, payload.path)
    except errors.FileNotFound as exc:
        raise exceptions.PathNotFound(path=payload.path) from exc


@router.post("/move_to_trash_batch", response_model=schemas.AsyncTaskID)
def move_to_trash_batch(
    payload: schemas.MoveToTrashBatchRequest,
    namespace: Namespace = Depends(deps.namespace),
):
    """
    Move several files or folders to Trash at once.

    To check task result use the same endpoint to check regular move result.
    """
    paths = [item.path for item in payload.items]
    task = tasks.move_to_trash_batch.delay(namespace, paths)
    return schemas.AsyncTaskID(async_task_id=task.id)


@router.post("/upload", response_model=schemas.UploadResult)
async def upload_file(
    file: UploadFile = FileParam(...),
    path: str = Form(...),
    db_pool: AsyncIOPool = Depends(deps.db_pool),
    namespace: Namespace = Depends(deps.namespace),
):
    """Upload file to a specified path."""
    if path == config.TRASH_FOLDER_NAME:
        raise exceptions.MalformedPath("Uploads to the Trash are not allowed")

    parents = Path(path).parents

    try:
        upload = await actions.save_file(db_pool, namespace, path, file.file)
    except errors.NotADirectory as exc:
        raise exceptions.NotADirectory(path=path) from exc

    updates = await crud.file.get_many(db_pool, namespace.path, parents)

    return schemas.UploadResult.construct(
        file=schemas.File.from_file(upload),
        updates=[schemas.File.from_file(f) for f in updates]
    )
