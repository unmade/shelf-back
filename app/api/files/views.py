from __future__ import annotations

import asyncio
import secrets
from datetime import datetime
from pathlib import Path

from cashews import cache
from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
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
    payload: schemas.FolderPath,
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
    except actions.AlreadyExists as exc:
        raise exceptions.AlreadyExists() from exc
    else:
        db_session.commit()

    return folder


@router.post("/delete_immediately", response_model=schemas.File)
def delete_immediately(
    payload: schemas.FolderPath,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    """Permanently deletes file or folder (recursively) with a given path."""
    if payload.path in (config.TRASH_FOLDER_NAME, "."):
        raise exceptions.InvalidOperation()

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


@router.post("/get_download_url", response_model=schemas.DownloadUrl)
async def get_download_url(
    request: Request,
    payload: schemas.FolderPath,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    """Generates and returns a link to download requested file or folder."""
    loop = asyncio.get_event_loop()
    file = await loop.run_in_executor(
        None, crud.file.get, db_session, account.namespace.id, payload.path
    )
    if not file:
        raise exceptions.PathNotFound()

    key = secrets.token_urlsafe()
    path = Path(account.namespace.path) / file.path
    await cache.set(key=key, value=path, expire=60)

    return {"download_url": f"{request.base_url}files/download?key={key}"}


@router.post("/list_folder", response_model=schemas.ListFolderResult)
def list_folder(
    payload: schemas.FolderPath,
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
    if (
        payload.from_path == payload.to_path
        or payload.from_path == config.TRASH_FOLDER_NAME
        or payload.to_path == config.TRASH_FOLDER_NAME
        or payload.from_path == "."
        or payload.to_path == "."
        or payload.to_path.startswith(f"{config.TRASH_FOLDER_NAME}/")
    ):
        raise exceptions.InvalidOperation()

    from_path = Path(payload.from_path)
    to_path = Path(payload.to_path)
    ns_path = Path(account.namespace.path)

    file = crud.file.get(db_session, account.namespace.id, str(from_path))
    if not file:
        raise exceptions.PathNotFound()

    if crud.file.get(db_session, account.namespace.id, str(to_path)):
        raise exceptions.AlreadyExists()

    next_parent = crud.file.get(db_session, account.namespace.id, str(to_path.parent))
    if not next_parent:
        storage.mkdir(ns_path / to_path.parent)
        next_parent = crud.file.create_parents(
            db_session,
            [storage.get(ns_path / p) for p in to_path.parents],
            namespace_id=account.namespace.id,
            rel_to=account.namespace.path,
        )

    file.parent_id = next_parent.id
    file.name = to_path.name
    crud.file.move(db_session, account.namespace.id, str(from_path), str(to_path))

    folders_to_decrease = set(from_path.parents).difference(to_path.parents)
    if folders_to_decrease:
        crud.file.inc_folders_size(
            db_session,
            account.namespace.id,
            paths=(str(p) for p in folders_to_decrease),
            size=-file.size,
        )

    folders_to_increase = set(to_path.parents).difference(from_path.parents)
    if folders_to_increase:
        crud.file.inc_folders_size(
            db_session,
            account.namespace.id,
            paths=(str(p) for p in folders_to_increase),
            size=file.size,
        )

    storage.move(ns_path / from_path, ns_path / to_path)
    db_session.commit()
    return file


@router.post("/move_to_trash", response_model=schemas.File)
def move_to_trash(
    payload: schemas.FolderPath,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    """Moves file to Trash folder."""
    if payload.path == config.TRASH_FOLDER_NAME:
        raise exceptions.InvalidOperation()
    if payload.path.startswith(f"{config.TRASH_FOLDER_NAME}/"):
        raise exceptions.AlreadyDeleted()

    from_path = Path(payload.path)
    to_path = Path(config.TRASH_FOLDER_NAME) / from_path.name
    ns_path = Path(account.namespace.path)

    file = crud.file.get(db_session, account.namespace.id, str(from_path))
    if not file:
        raise exceptions.PathNotFound()

    if crud.file.get(db_session, account.namespace.id, str(to_path)):
        name = to_path.name.strip(to_path.suffix)
        suffix = datetime.now().strftime("%H%M%S%f")
        to_path = to_path.parent / f"{name} {suffix}{to_path.suffix}"

    next_parent = crud.file.get(db_session, account.namespace.id, str(to_path.parent))

    file.parent_id = next_parent.id
    file.name = to_path.name
    crud.file.move(db_session, account.namespace.id, str(from_path), str(to_path))

    folders_to_decrease = set(from_path.parents).difference(to_path.parents)
    if folders_to_decrease:
        crud.file.inc_folders_size(
            db_session,
            account.namespace.id,
            paths=(str(p) for p in folders_to_decrease),
            size=-file.size,
        )

    folders_to_increase = set(to_path.parents).difference(from_path.parents)
    if folders_to_increase:
        crud.file.inc_folders_size(
            db_session,
            account.namespace.id,
            paths=(str(p) for p in folders_to_increase),
            size=file.size,
        )

    storage.move(ns_path / from_path, ns_path / to_path)
    db_session.commit()
    return file


@router.post("/upload", response_model=schemas.UploadResult)
def upload_file(
    file: UploadFile = File(...),
    path: str = Form(...),
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    """
    Uploads file to a specified path.

    Note, that if file with the same name already exists, it will be overriden.
    """
    if path == config.TRASH_FOLDER_NAME:
        raise exceptions.InvalidOperation()

    relpath = Path(path)
    ns_path = Path(account.namespace.path)
    fullpath = ns_path / relpath

    if not storage.is_dir_exists(fullpath.parent):
        # todo: catch exception if creation fails
        storage.mkdir(fullpath.parent)

    parent = crud.file.get_folder(db_session, account.namespace.id, str(relpath.parent))
    if not parent:
        parent = crud.file.create_parents(
            db_session,
            [storage.get(ns_path / p) for p in relpath.parents],
            namespace_id=account.namespace.id,
            rel_to=account.namespace.path,
        )

    file_exists = storage.is_exists(fullpath)
    storage_file = storage.save(fullpath, file.file)

    if file_exists:
        prev_file = storage.get(fullpath)
        result = crud.file.update(
            db_session,
            storage_file,
            namespace_id=account.namespace.id,
            rel_to=account.namespace.path,
        )
        size_inc = storage_file.size - prev_file.size
    else:
        result = crud.file.create(
            db_session,
            storage_file,
            namespace_id=account.namespace.id,
            rel_to=account.namespace.path,
            parent_id=parent.id,
        )
        size_inc = storage_file.size

    crud.file.inc_folder_size(
        db_session, namespace_id=account.namespace.id, path=result.path, size=size_inc,
    )

    db_session.commit()
    db_session.refresh(result)

    return schemas.UploadResult(
        file=result,
        updates=crud.file.list_parents(db_session, account.namespace.id, path),
    )
