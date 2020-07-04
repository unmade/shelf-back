from fastapi import APIRouter, Depends

from app import db
from app.auth.deps import get_current_user
from app.users.models import User

from . import crud

router = APIRouter()


@router.get("")
def list_files(path: str = None, curr_user: User = Depends(get_current_user)):
    with db.SessionManager() as db_session:
        files = crud.ls_root(db_session, curr_user, path)

    return {
        "files": [
            {
                "type": file.type,
                "id": file.id,
                "name": file.name,
                "size": file.size,
                "mtime": file.mtime,
                "path": file.path,
            }
            for file in files
        ],
        "count": len(files),
    }
