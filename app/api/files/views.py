from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app import crud
from app.api import deps, exceptions
from app.entities.account import Account
from app.storage import storage

from .schemas import FolderPath, ListFolderResult, UploadResult

router = APIRouter()


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
        storage.mkdir(fullpath.parent)

    dir_exists = crud.file.is_dir_exists(db_session, account.namespace.id, str(relpath))
    if not dir_exists:
        parent = crud.file.create_parents(
            db_session,
            [storage.get(ns_path.joinpath(p)) for p in relpath.parents],
            namespace_id=account.namespace.id,
            rel_to=account.namespace.path,
        )
    else:
        parent = crud.file.get_folder(db_session, account.namespace.id, str(relpath))

    storage_file = storage.save(fullpath, file.file)

    result = crud.file.create(
        db_session,
        storage_file,
        namespace_id=account.namespace.id,
        rel_to=account.namespace.path,
        parent_id=parent.id,
    )
    crud.file.inc_folder_size(
        db_session,
        namespace_id=account.namespace.id,
        path=result.path,
        size=storage_file.size,
    )

    db_session.commit()
    db_session.refresh(result)

    return result
