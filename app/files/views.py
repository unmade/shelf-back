from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from app import crud, db
from app.auth.deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("")
def list_files(path: str = None, curr_user: User = Depends(get_current_user)):
    with db.SessionManager() as db_session:
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
