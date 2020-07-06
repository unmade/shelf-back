from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import aliased

from app.models.file import File
from app.storage import StorageFile

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def get(db_session: Session, namespace_id: int, path: str) -> Optional[File]:
    return (
        db_session.query(File)
        .filter(File.namespace_id == namespace_id, File.path == str(path))
        .first()
    )


def ls(db_session: Session, namespace_id: int, path: Optional[str]):
    query = db_session.query(File)
    if path:
        parent = aliased(File)
        query = query.join(parent, File.parent_id == parent.id).filter(
            parent.namespace_id == namespace_id, parent.path == path
        )
    else:
        query = query.filter(
            File.namespace_id == namespace_id, File.parent_id.is_(None)
        )
    return query.order_by(File.is_dir.desc(), File.name.asc()).all()


def create(
    db_session: Session,
    storage_file: StorageFile,
    namespace_id: int,
    parent_id: Optional[int] = None,
) -> File:
    file = File(
        namespace_id=namespace_id,
        parent_id=parent_id,
        type=0 if storage_file.is_dir() else 1,
        name=storage_file.name,
        path=storage_file.path,
        size=storage_file.size,
        mtime=storage_file.mtime,
        is_dir=storage_file.is_dir(),
    )
    db_session.add(file)

    return file
