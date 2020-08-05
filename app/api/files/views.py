from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app import crud
from app.api import deps, exceptions
from app.entities.account import Account
from app.storage import storage

from .schemas import (
    CreateFolderResult,
    FolderPath,
    ListFolderResult,
    MoveFolderRequest,
    MoveFolderResult,
    UploadResult,
)

router = APIRouter()


@router.post("/create_folder", response_model=CreateFolderResult)
def create_folder(
    payload: FolderPath,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
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


@router.post("/move", response_model=MoveFolderResult)
def move(
    payload: MoveFolderRequest,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
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


@router.post("/list_folder", response_model=ListFolderResult)
def list_folder(
    payload: FolderPath,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    folder = crud.file.get_folder(db_session, account.namespace.id, payload.path)
    if not folder:
        raise exceptions.PathNotFound()

    files = crud.file.list_folder_by_id(db_session, folder.id)

    return ListFolderResult(path=payload.path, items=files, count=len(files))


@router.post("/upload", response_model=UploadResult)
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

    return UploadResult(
        file=result,
        updates=crud.file.list_parents(db_session, account.namespace.id, path),
    )
