from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from sqlalchemy.orm import aliased

from app.models.file import File

if TYPE_CHECKING:
    from pathlib import Path
    from sqlalchemy.orm import Session


def get(db_session: Session, namespace_id: int, path: str) -> Optional[File]:
    return (
        db_session.query(File)
        .filter(
            File.namespace_id == namespace_id,
            File.path == str(path),
        )
        .first()
    )


def ls(db_session: Session, namespace_id: int, path: Optional[str]):
    if path:
        parent = aliased(File)
        return  (
            db_session.query(File)
            .join(parent, File.parent_id == parent.id)
            .filter(parent.namespace_id == namespace_id, parent.path == path)
            .all()
        )
    return (
        db_session.query(File)
        .filter(File.namespace_id == namespace_id, File.parent_id.is_(None))
        .all()
    )


def create_from_path(
    db_session: Session,
    path: Path,
    namespace_id: int,
    parent_id: Optional[int] = None,
    rel_to: Union[None, str, Path] = None,
) -> File:
    stat = path.lstat()
    file = File(
        namespace_id=namespace_id,
        parent_id=parent_id,
        type=0 if path.is_dir() else 1,
        name=path.name,
        path=str(path.relative_to(rel_to) if rel_to else path),
        size=stat.st_size,
        mtime=stat.st_mtime,
        is_dir=path.is_dir(),
    )
    db_session.add(file)

    return file
