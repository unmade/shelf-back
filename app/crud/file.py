from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional, Union

from sqlalchemy.orm import Session, aliased

from app.models.file import File
from app.storage import StorageFile


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


def list_folder(db_session: Session, namespace_id: int, path: str):
    parent = aliased(File)
    return (
        db_session.query(File)
        .join(parent, parent.id == File.parent_id)
        .filter(
            parent.namespace_id == namespace_id,
            parent.path == path,
            parent.is_dir.is_(True),
        )
        .order_by(File.is_dir.desc(), File.name.asc())
        .all()
    )


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
    parent_id: int = None,
) -> File:
    file = File(
        namespace_id=namespace_id,
        parent_id=parent_id,
        name=storage_file.name,
        path=str(storage_file.path.relative_to(rel_to)),
        size=0 if storage_file.is_dir() else storage_file.size,
        mtime=storage_file.mtime,
        is_dir=storage_file.is_dir(),
    )
    db_session.add(file)

    return file


def bulk_create(
    db_session: Session,
    storage_files: Iterator[StorageFile],
    namespace_id: int,
    rel_to: Union[str, Path],
    parent_id: int,
) -> None:
    db_session.bulk_insert_mappings(
        File,
        (
            dict(
                namespace_id=namespace_id,
                parent_id=parent_id,
                name=storage_file.name,
                path=str(storage_file.path.relative_to(rel_to)),
                size=0 if storage_file.is_dir() else storage_file.size,
                mtime=storage_file.mtime,
                is_dir=storage_file.is_dir(),
            )
            for storage_file in storage_files
        ),
    )


def inc_folder_size(
    db_session: Session, namespace_id: int, path: str, size: int,
):
    parents = (str(p) for p in Path(path).parents)
    return (
        db_session.query(File)
        .filter(
            File.namespace_id == namespace_id,
            File.is_dir.is_(True),
            File.path.in_([path, *parents]),
        )
        .update({"size": File.size + size}, synchronize_session=False)
    )
