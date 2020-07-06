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
def list_files(
    folder: FolderPath,
    db_session: Session = Depends(deps.db_session),
    account: Account = Depends(deps.current_account),
):
    files = crud.file.ls(db_session, account.namespace_id, folder.path)

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
    parent_id = None
    if path:
        parent = crud.file.get(db_session, account.namespace_id, path)
        if not parent:
            raise exceptions.PathNotFound()
        parent_id = parent.id

    fdest = Path(path).joinpath(file.filename) if path else file.filename
    storage_file = storage.save(account.username, fdest, file)
    crud.file.create(db_session, storage_file, account.namespace_id, parent_id)
    db_session.commit()

    return {"filename": file.filename, "path": path}
