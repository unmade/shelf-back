from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

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


def get_folder(db_session: Session, namespace_id: int, path: str):
    return (
        db_session.query(File)
        .filter(
            File.namespace_id == namespace_id, File.path == path, File.is_dir.is_(True)
        )
        .first()
    )


def list_folder(db_session: Session, namespace_id: int, path: Optional[str] = None):
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


def list_folder_by_id(db_session: Session, folder_id: Optional[int]):
    return (
        db_session.query(File)
        .filter(File.parent_id == folder_id)
        .order_by(File.is_dir.desc(), File.name.asc())
        .all()
    )


def create(
    db_session: Session,
    storage_file: StorageFile,
    namespace_id: int,
    rel_to: Union[str, Path],
    parent_id: Optional[int] = None,
) -> File:
    file = File(
        namespace_id=namespace_id,
        parent_id=parent_id,
        type=0 if storage_file.is_dir() else 1,
        name=storage_file.name,
        path=str(storage_file.path.relative_to(rel_to)),
        size=storage_file.size,
        mtime=storage_file.mtime,
        is_dir=storage_file.is_dir(),
    )
    db_session.add(file)

    return file
