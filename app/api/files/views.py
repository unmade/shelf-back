from __future__ import annotations

import asyncio
import secrets
from pathlib import Path

from cashews import cache
from fastapi import APIRouter, Depends
from fastapi import File as FileParam
from fastapi import Form, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import actions, config, crud
from app.api import deps
from app.entities import Account
from app.storage import storage

from . import exceptions, schemas

router = APIRouter()


@router.post("/create_folder", response_model=schemas.File)
def create_folder(
    payload: schemas.PathRequest,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    """
    Creates a new folder within a given path.

    If a path provided in a format a/b/c, then 'a' and 'b' folders will be created,
    if not existed, and 'c' will be returned as a response.
    """
    try:
        folder = actions.create_folder(db_session, account.namespace, payload.path)
    except actions.FileAlreadyExists as exc:
        raise exceptions.AlreadyExists() from exc
    else:
        db_session.commit()

    return folder


@router.post("/delete_immediately", response_model=schemas.File)
def delete_immediately(
    payload: schemas.PathRequest,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    """Permanently deletes file or folder (recursively) with a given path."""
    if payload.path in (config.TRASH_FOLDER_NAME, "."):
        raise exceptions.InvalidPath()

    try:
        file = actions.delete_immediately(db_session, account.namespace, payload.path)
    except actions.FileNotFound as exc:
        raise exceptions.PathNotFound() from exc
    else:
        db_session.commit()

    return file


@router.get("/download")
async def download(key: str = Query(None)):
    """Downloads a file or a folder as a ZIP archive."""
    path = await cache.get(key)
    if not path:
        raise exceptions.DownloadNotFound()

    await cache.delete(key)

    filename = Path(path).name.encode("utf-8").decode("latin-1")
    headers = {"Content-Disposition": f'attachment; filename="{filename}.zip"'}
    attachment = storage.download(path)
    return StreamingResponse(attachment, media_type="attachment/zip", headers=headers)


@router.post("/empty_trash", response_model=schemas.File)
def empty_trash(
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    """Deletes all files and folders in the Trash folder."""
    trash_folder = actions.empty_trash(db_session, account.namespace)
    db_session.commit()
    return trash_folder


@router.post("/get_download_url", response_model=schemas.GetDownloadUrlResult)
async def get_download_url(
    request: Request,
    payload: schemas.PathRequest,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    """Generates and returns a link to download requested file or folder."""
    loop = asyncio.get_event_loop()
    file_exists = await loop.run_in_executor(
        None, crud.file.exists, db_session, account.namespace.id, payload.path,
    )
    if not file_exists:
        raise exceptions.PathNotFound()

    key = secrets.token_urlsafe()
    path = account.namespace.path / payload.path
    await cache.set(key=key, value=path, expire=60)

    return {"download_url": f"{request.base_url}files/download?key={key}"}


@router.post("/list_folder", response_model=schemas.ListFolderResult)
def list_folder(
    payload: schemas.PathRequest,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    """
    Lists content of a folder with a given path.

    Note, that Trash folder is never present in a result list.
    """
    folder = crud.file.get_folder(db_session, account.namespace.id, payload.path)
    if not folder:
        raise exceptions.PathNotFound()

    files = crud.file.list_folder_by_id(db_session, folder.id, hide_trash_folder=True)

    return schemas.ListFolderResult(path=payload.path, items=files, count=len(files))


@router.post("/move", response_model=schemas.File)
def move(
    payload: schemas.MoveFolderRequest,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    """
    Moves file or a folder (including content) to a new path.

    The last part of a new path would become new file/folder name.
    For example, to rename file with path 'file.txt', the new path should be
    'renamed_file.txt'.

    Note, this method doesn't allow to move file/folder to/from Trash folder.
    """
    try:
        file = actions.move(
            db_session, account.namespace, payload.from_path, payload.to_path,
        )
    except actions.FileAlreadyExists as exc:
        raise exceptions.AlreadyExists() from exc
    except actions.FileNotFound as exc:
        raise exceptions.PathNotFound from exc
    else:
        db_session.commit()

    return file


@router.post("/move_to_trash", response_model=schemas.File)
def move_to_trash(
    payload: schemas.PathRequest,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    """Moves file to Trash folder."""
    if payload.path == config.TRASH_FOLDER_NAME:
        raise exceptions.InvalidPath()
    if payload.path.startswith(f"{config.TRASH_FOLDER_NAME}/"):
        raise exceptions.AlreadyDeleted()

    try:
        file = actions.move_to_trash(db_session, account.namespace, payload.path)
    except actions.FileNotFound as exc:
        raise exceptions.PathNotFound from exc
    else:
        db_session.commit()

    return file


@router.post("/upload", response_model=schemas.UploadResult)
def upload_file(
    file: UploadFile = FileParam(...),
    path: str = Form(...),
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    """
    Uploads file to a specified path.

    Note, that if file with the same name already exists, it will be overriden.
    """
    if path == config.TRASH_FOLDER_NAME:
        raise exceptions.InvalidPath()

    saved_file = actions.save_file(db_session, account.namespace, path, file.file)
    db_session.commit()

    return schemas.UploadResult(
        file=saved_file,
        updates=crud.file.list_parents(db_session, account.namespace.id, path),
    )
