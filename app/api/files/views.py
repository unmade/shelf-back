from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app import crud
from app.api import deps
from app.models.user import User

router = APIRouter()


@router.get("")
def list_files(
    path: str = None,
    db_session: Session = Depends(deps.db_session),
    curr_user: User = Depends(deps.current_user),
):
    namespace = crud.namespace.get(db_session, owner_id=curr_user.id)
    files = crud.file.ls(db_session, namespace.id, path)

    return {
        "files": [
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


@router.post("")
def upload_file(file: UploadFile = File(...)):
    return {"filename": file.filename}
