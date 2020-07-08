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

    return ListFolderResult(items=files, count=len(files))


@router.post("/upload", response_model=UploadResult)
def upload_file(
    file: UploadFile = File(...),
    path: str = Form(...),
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    parent = crud.file.get_folder(db_session, account.namespace.id, path)
    if not parent:
        raise exceptions.PathNotFound()

    fpath = Path(account.namespace.path).joinpath(path).joinpath(file.filename)
    storage_file = storage.save(account.username, fpath, file.file)
    result = crud.file.create(
        db_session,
        storage_file,
        account.namespace.id,
        account.namespace.path,
        parent.id,
    )
    db_session.commit()

    return result
