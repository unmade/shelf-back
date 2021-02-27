from __future__ import annotations

import secrets
from pathlib import Path

from cashews import cache
from edgedb import AsyncIOConnection
from fastapi import APIRouter, Depends
from fastapi import File as FileParam
from fastapi import Form, Query, Request, UploadFile
from fastapi.responses import StreamingResponse

from app import actions, config, crud, errors
from app.api import deps
from app.entities import User
from app.storage import storage

from . import exceptions, schemas

router = APIRouter()


@router.post("/create_folder", response_model=schemas.File)
async def create_folder(
    payload: schemas.PathRequest,
    db_conn: AsyncIOConnection = Depends(deps.db_conn),
    user: User = Depends(deps.current_user),
):
    """
    Create a new folder with a target path.

    Any missing parents of the folder path are created as needed.
    If a path provided in a format 'a/b/c', then 'a' and 'b' folders will be created,
    if not existed, and 'c' will be returned as a response.
    """
    try:
        return await actions.create_folder(db_conn, user.namespace, payload.path)
    except errors.FileAlreadyExists as exc:
        raise exceptions.AlreadyExists() from exc
    except errors.NotADirectory as exc:
        raise exceptions.InvalidPath() from exc


@router.post("/delete_immediately", response_model=schemas.File)
async def delete_immediately(
    payload: schemas.PathRequest,
    db_conn: AsyncIOConnection = Depends(deps.db_conn),
    user: User = Depends(deps.current_user),
):
    """Permanently delete file or folder with its contents"""
    if payload.path in (config.TRASH_FOLDER_NAME, "."):
        raise exceptions.InvalidPath()

    try:
        return await actions.delete_immediately(db_conn, user.namespace, payload.path)
    except errors.FileNotFound as exc:
        raise exceptions.PathNotFound() from exc


@router.get("/download")
async def download(key: str = Query(None)):
    """Download a file or a folder as a ZIP archive"""
    path = await cache.get(key)
    if not path:
        raise exceptions.DownloadNotFound()

    await cache.delete(key)

    filename = Path(path).name.encode("utf-8").decode("latin-1")
    headers = {"Content-Disposition": f'attachment; filename="{filename}.zip"'}
    attachment = storage.download(path)
    return StreamingResponse(attachment, media_type="attachment/zip", headers=headers)


@router.post("/empty_trash", response_model=schemas.File)
async def empty_trash(
    db_conn: AsyncIOConnection = Depends(deps.db_conn),
    user: User = Depends(deps.current_user),
):
    """Delete all files and folders in the Trash folder."""
    return await actions.empty_trash(db_conn, user.namespace)


@router.post("/get_download_url", response_model=schemas.GetDownloadUrlResult)
async def get_download_url(
    request: Request,
    payload: schemas.PathRequest,
    db_conn: AsyncIOConnection = Depends(deps.db_conn),
    user: User = Depends(deps.current_user),
):
    """Return a link to download requested file or folder."""
    if not await crud.file.exists(db_conn, user.namespace.path, payload.path):
        raise exceptions.PathNotFound()

    key = secrets.token_urlsafe()
    path = user.namespace.path / payload.path
    await cache.set(key=key, value=path, expire=60)

    return {"download_url": f"{request.base_url}files/download?key={key}"}


@router.post("/get_thumbnail")
async def get_thumbnail(
    payload: schemas.PathRequest,
    size: schemas.ThumbnailSize = schemas.ThumbnailSize.xs,
    conn: AsyncIOConnection = Depends(deps.db_conn),
    user: User = Depends(deps.current_user),
):
    """Generate thumbnail for an image file."""
    path = payload.path
    try:
        file, disksize, thumbnail = (
            await actions.get_thumbnail(conn, user.namespace, path, size=size.asint())
        )
    except errors.FileNotFound as exc:
        raise exceptions.PathNotFound() from exc
    except (errors.IsADirectory, errors.ThumbnailUnavailable) as exc:
        raise exceptions.InvalidPath() from exc
    headers = {
        "Content-Disposition": f'inline; filename="{file.name}"',
        "Content-Length": str(disksize),
    }
    return StreamingResponse(thumbnail, headers=headers, media_type=file.mediatype)


@router.post("/list_folder", response_model=schemas.ListFolderResult)
async def list_folder(
    payload: schemas.PathRequest,
    db_conn: AsyncIOConnection = Depends(deps.db_conn),
    user: User = Depends(deps.current_user),
):
    """
    List content of a folder with a given path.

    Note, that Trash folder is never present in a result.
    """
    try:
        files = await crud.file.list_folder(db_conn, user.namespace.path, payload.path)
    except errors.FileNotFound as exc:
        raise exceptions.PathNotFound() from exc
    except errors.NotADirectory as exc:
        raise exceptions.InvalidPath() from exc  # todo: this should be more informative

    return schemas.ListFolderResult.construct(
        path=payload.path,
        items=[schemas.File.from_file(f) for f in files],
        count=len(files)
    )


@router.post("/move", response_model=schemas.File)
async def move(
    payload: schemas.MoveFolderRequest,
    db_conn: AsyncIOConnection = Depends(deps.db_conn),
    user: User = Depends(deps.current_user),
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
        return await actions.move(db_conn, user.namespace, from_path, to_path)
    except errors.FileAlreadyExists as exc:
        raise exceptions.AlreadyExists() from exc
    except errors.FileNotFound as exc:
        raise exceptions.PathNotFound() from exc
    except (errors.MissingParent, errors.NotADirectory) as exc:
        raise exceptions.InvalidPath() from exc


@router.post("/move_to_trash", response_model=schemas.File)
async def move_to_trash(
    payload: schemas.PathRequest,
    db_conn: AsyncIOConnection = Depends(deps.db_conn),
    user: User = Depends(deps.current_user),
):
    """Move file to the Trash folder."""
    if payload.path == config.TRASH_FOLDER_NAME:
        raise exceptions.InvalidPath()
    if payload.path.startswith(f"{config.TRASH_FOLDER_NAME}/"):
        raise exceptions.AlreadyDeleted()

    try:
        return await actions.move_to_trash(db_conn, user.namespace, payload.path)
    except errors.FileNotFound as exc:
        raise exceptions.PathNotFound() from exc


@router.post("/upload", response_model=schemas.UploadResult)
async def upload_file(
    file: UploadFile = FileParam(...),
    path: str = Form(...),
    db_conn: AsyncIOConnection = Depends(deps.db_conn),
    user: User = Depends(deps.current_user),
):
    """Upload file to a specified path."""
    if path == config.TRASH_FOLDER_NAME:
        raise exceptions.InvalidPath()

    parents = Path(path).parents

    upload = await actions.save_file(db_conn, user.namespace, path, file.file)
    updates = await crud.file.get_many(db_conn, user.namespace.path, parents)

    return schemas.UploadResult.construct(
        file=schemas.File.from_file(upload),
        updates=[schemas.File.from_file(f) for f in updates]
    )
