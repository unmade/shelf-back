from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from pathlib import Path

from cashews import cache
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import config, crud
from app.api import deps
from app.entities.account import Account
from app.storage import storage

from . import exceptions, schemas

router = APIRouter()


@router.post("/create_folder", response_model=schemas.CreateFolderResult)
def create_folder(
    payload: schemas.FolderPath,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    # TODO: don't forget to strip input path
    relpath = Path(payload.path)
    ns_path = Path(account.namespace.path)
    fullpath = ns_path.joinpath(relpath)

    if storage.is_dir_exists(fullpath):
        raise exceptions.AlreadyExists()

    # todo: catch exception if creation fails
    storage.mkdir(fullpath)

    parent = crud.file.get_folder(db_session, account.namespace.id, str(relpath.parent))
    if not parent:
        parent = crud.file.create_parents(
            db_session,
            [storage.get(ns_path.joinpath(p)) for p in relpath.parents],
            namespace_id=account.namespace.id,
            rel_to=account.namespace.path,
        )

    storage_file = storage.get(fullpath)
    folder = crud.file.create(
        db_session,
        storage_file,
        account.namespace.id,
        rel_to=account.namespace.path,
        parent_id=parent.id,
    )
    db_session.commit()

    return folder


@router.post("/move", response_model=schemas.MoveFolderResult)
def move(
    payload: schemas.MoveFolderRequest,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    if (
        payload.from_path == payload.to_path
        or payload.from_path == config.TRASH_FOLDER_NAME
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
        next_parent = crud.file.create_parents(
            db_session,
            [storage.get(ns_path.joinpath(p)) for p in to_path.parents],
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

    storage.move(ns_path.joinpath(from_path), ns_path.joinpath(to_path))
    db_session.commit()
    return file


@router.post("/list_folder", response_model=schemas.ListFolderResult)
def list_folder(
    payload: schemas.FolderPath,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    folder = crud.file.get_folder(db_session, account.namespace.id, payload.path)
    if not folder:
        raise exceptions.PathNotFound()

    files = crud.file.list_folder_by_id(db_session, folder.id, hide_trash_folder=True)

    return schemas.ListFolderResult(path=payload.path, items=files, count=len(files))


@router.post("/upload", response_model=schemas.UploadResult)
def upload_file(
    file: UploadFile = File(...),
    path: str = Form(...),
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    relpath = Path(path)
    ns_path = Path(account.namespace.path)
    fullpath = ns_path.joinpath(relpath)

    if not storage.is_dir_exists(fullpath.parent):
        # todo: catch exception if creation fails
        storage.mkdir(fullpath.parent)

    parent = crud.file.get_folder(db_session, account.namespace.id, str(relpath.parent))
    if not parent:
        parent = crud.file.create_parents(
            db_session,
            [storage.get(ns_path.joinpath(p)) for p in relpath.parents],
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


@router.post("/delete", response_model=schemas.MoveToTrashResult)
def delete(
    payload: schemas.FolderPath,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    if payload.path == config.TRASH_FOLDER_NAME:
        raise exceptions.InvalidOperation()
    if payload.path.startswith(config.TRASH_FOLDER_NAME):
        raise exceptions.AlreadyDeleted()

    from_path = Path(payload.path)
    to_path = Path(config.TRASH_FOLDER_NAME).joinpath(from_path.name)
    ns_path = Path(account.namespace.path)

    file = crud.file.get(db_session, account.namespace.id, str(from_path))
    if not file:
        raise exceptions.PathNotFound()

    if crud.file.get(db_session, account.namespace.id, str(to_path)):
        name = to_path.name.strip(to_path.suffix)
        suffix = datetime.now().strftime("%H%M%S%f")
        to_path = to_path.parent.joinpath(f"{name} {suffix}{to_path.suffix}")

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

    storage.move(ns_path.joinpath(from_path), ns_path.joinpath(to_path))
    db_session.commit()
    return file


@router.post("/delete_immediately")
def delete_immediately(
    payload: schemas.FolderPath,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    file = crud.file.get(db_session, account.namespace.id, payload.path)
    if not file:
        raise exceptions.PathNotFound()

    crud.file.inc_folders_size(
        db_session,
        account.namespace.id,
        paths=(str(p) for p in Path(payload.path).parents),
        size=-file.size,
    )

    crud.file.delete(db_session, account.namespace.id, payload.path)
    storage.delete(Path(account.namespace.path).joinpath(payload.path))

    db_session.commit()

    return file


@router.post("/empty_trash")
def empty_trash(
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    crud.file.empty_trash(db_session, account.namespace.id)
    storage.delete_dir_content(
        Path(account.namespace.path).joinpath(config.TRASH_FOLDER_NAME)
    )

    db_session.commit()

    return {}


@router.post("/get_download_url")
async def get_download_url(
    payload: schemas.FolderPath,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    loop = asyncio.get_event_loop()
    file = await loop.run_in_executor(
        None, crud.file.get, db_session, account.namespace.id, payload.path
    )
    if not file:
        raise exceptions.PathNotFound()

    key = uuid.uuid4().hex
    path = Path(account.namespace.path).joinpath(file.path)
    await cache.set(key=key, value=path, expire=60)

    return {"download_url": f"http://localhost:8000/files/download?key={key}"}


@router.get("/download")
async def download(key: str = Query(None)):
    path = await cache.get(key)
    if not path:
        raise exceptions.DownloadNotFound()

    await cache.delete(key)

    filename = Path(path).name.encode("utf-8").decode("latin-1")
    headers = {"Content-Disposition": f'attachment; filename="{filename}.zip"'}
    attachment = storage.download(path)
    return StreamingResponse(attachment, media_type="attachment/zip", headers=headers)
