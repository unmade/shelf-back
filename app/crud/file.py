from __future__ import annotations

import operator
from pathlib import Path
from typing import Iterable, Optional, Union

import sqlalchemy.exc
from sqlalchemy.orm import Session, aliased

from app.models.file import File
from app.storage import StorageFile


def get(db_session: Session, namespace_id: int, path: str) -> Optional[File]:
    return (
        db_session.query(File)
        .filter(File.namespace_id == namespace_id, File.path == str(path))
        .scalar()
    )


def get_folder(db_session: Session, namespace_id: int, path: str) -> Optional[File]:
    return (
        db_session.query(File)
        .filter(
            File.namespace_id == namespace_id, File.path == path, File.is_dir.is_(True)
        )
        .scalar()
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
    storage_files: Iterable[StorageFile],
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
            File.path.in_([path, *parents]),
            File.is_dir.is_(True),
        )
        .update({"size": File.size + size}, synchronize_session=False)
    )


def list_parents(
    db_session: Session, namespace_id: int, path: str,
):
    parents = (str(p) for p in Path(path).parents)
    return (
        db_session.query(File)
        .filter(
            File.namespace_id == namespace_id,
            File.path.in_(parents),
            File.is_dir.is_(True),
        )
        .order_by(File.path.asc())
        .all()
    )


def create_parents(
    db_session: Session, parents: Iterable[StorageFile], namespace_id: int, rel_to: str
) -> File:
    parents_in_db = (
        db_session.query(File.id, File.path)
        .filter(
            File.namespace_id == namespace_id,
            File.path.in_(str(p.path.relative_to(rel_to)) for p in parents),
            File.is_dir.is_(True),
        )
        .order_by(File.path.asc())
        .all()
    )
    paths = set(item.path for item in parents_in_db)
    new_parents = sorted(
        (p for p in parents if str(p.path.relative_to(rel_to)) not in paths),
        key=operator.attrgetter("path"),
    )
    parent = parents_in_db[-1]
    for storage_file in new_parents:
        parent = create(
            db_session, storage_file, namespace_id, rel_to=rel_to, parent_id=parent.id,
        )
        try:
            # we want to commit this earlier, so other requests
            # can see changes
            db_session.commit()
        except sqlalchemy.exc.IntegrityError:
            # this folder already created by other request,
            # so just refetch the right parent
            db_session.rollback()
            parent = get_folder(
                db_session, namespace_id, str(storage_file.path.relative_to(rel_to))
            )
            if not parent:
                raise Exception("Failed to create parent")

    return parent


def update(
    db_session: Session,
    storage_file: StorageFile,
    namespace_id: int,
    rel_to: Union[str, Path],
) -> File:
    file = get(db_session, namespace_id, str(storage_file.path.relative_to(rel_to)))

    file.size = storage_file.size
    file.mtime = storage_file.mtime
    db_session.add(file)

    return file
