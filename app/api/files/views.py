from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app import crud
from app.api import deps, exceptions
from app.entities.account import Account
from app.storage import storage

from .schemas import FolderPath

router = APIRouter()


@router.post("/list")
def list_folder(
    payload: FolderPath,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    if payload.path:
        folder = crud.file.get_folder(db_session, account.namespace.id, payload.path)
        if not folder:
            raise exceptions.PathNotFound()

        files = crud.file.list_folder_by_id(db_session, folder.id)
    else:
        files = crud.file.list_folder(db_session, account.namespace.id)

    return {
        "items": [
            {
                "id": file.id,
                "type": file.type,
                "name": file.name,
                "size": file.size,
                "mtime": file.mtime,
                "path": file.path,
            }
            for file in files
        ],
        "count": len(files),
    }


@router.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    path: Optional[str] = Form(None),
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    fpath = Path(account.namespace.path)
    parent_id = None
    if path:
        parent = crud.file.get_folder(db_session, account.namespace.id, path)
        if not parent:
            raise exceptions.PathNotFound()
        parent_id = parent.id
        fpath.joinpath(path)

    fpath = fpath.joinpath(file.filename)
    storage_file = storage.save(account.username, fpath, file.file)
    crud.file.create(
        db_session,
        storage_file,
        account.namespace.id,
        account.namespace.path,
        parent_id,
    )
    db_session.commit()

    return {"filename": file.filename, "path": path}
