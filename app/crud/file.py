from __future__ import annotations

import operator
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

import sqlalchemy.exc
from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from app.config import TRASH_FOLDER_NAME
from app.models import File
from app.storage import StorageFile

if TYPE_CHECKING:
    from app.typedefs import StrOrPath


def exists(
    db_session: Session, namespace_id: int, path: StrOrPath, folder: bool = None
) -> bool:
    """
    Checks whether a file or a folder exists in a given path.

    Args:
        db_session (Session): Database session.
        namespace_id (int): Namespace where to look for a path.
        path (StrOrPath): Path to a file or a folder.
        folder (bool, optional): If True, will check only if folder exists, otherwise
            will check for a file. If None (default) will check for both.

    Returns:
        bool: True if file/folder exists, False otherwise.
    """
    query = (
        db_session.query(File)
        .filter(
            File.namespace_id == namespace_id,
            File.path == str(path),
        )
    )
    if folder is not None:
        query = query.filter(File.is_dir.is_(folder))
    return db_session.query(query.exists()).scalar()


def get(db_session: Session, namespace_id: int, path: StrOrPath) -> File:
    return (
        db_session.query(File)
        .filter(
            File.namespace_id == namespace_id,
            File.path == str(path),
        )
        .scalar()
    )


def get_folder(db_session: Session, namespace_id: int, path: StrOrPath) -> File:
    return (
        db_session.query(File)
        .filter(
            File.namespace_id == namespace_id,
            File.path == str(path),
            File.is_dir.is_(True)
        )
        .scalar()
    )


def list_folder(db_session: Session, namespace_id: int, path: StrOrPath):
    parent = aliased(File)
    return (
        db_session.query(File)
        .join(parent, parent.id == File.parent_id)
        .filter(
            parent.namespace_id == namespace_id,
            parent.path == str(path),
            parent.is_dir.is_(True),
        )
        .order_by(File.is_dir.desc(), File.name.collate("NOCASE"))
        .all()
    )


def list_folder_by_id(
    db_session: Session, folder_id: int, hide_trash_folder: bool = False,
):
    query = (
        db_session.query(File)
        .filter(File.parent_id == folder_id)
        .order_by(File.is_dir.desc(), File.name.collate("NOCASE"))
    )
    if hide_trash_folder:
        query = query.filter(File.path != TRASH_FOLDER_NAME)
    return query.all()


def create(
    db_session: Session,
    storage_file: StorageFile,
    namespace_id: int,
    rel_to: StrOrPath,
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
    db_session.flush()

    return file


def bulk_create(
    db_session: Session,
    storage_files: Iterable[StorageFile],
    namespace_id: int,
    rel_to: StrOrPath,
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
    db_session: Session, namespace_id: int, path: StrOrPath, size: int,
):
    parents = (str(p) for p in Path(path).parents)
    return (
        db_session.query(File)
        .filter(
            File.namespace_id == namespace_id,
            File.path.in_([str(path), *parents]),
            File.is_dir.is_(True),
        )
        .update({"size": File.size + size}, synchronize_session=False)
    )


def list_parents(
    db_session: Session, namespace_id: int, path: StrOrPath,
):
    parents = (str(p) for p in Path(path).parents)
    return (
        db_session.query(File)
        .filter(
            File.namespace_id == namespace_id,
            File.path.in_(parents),
            File.is_dir.is_(True),
        )
        .order_by(File.path.collate("NOCASE"))
        .all()
    )


def create_parents(
    db_session: Session,
    parents: Iterable[StorageFile],
    namespace_id: int,
    rel_to: StrOrPath,
) -> File:
    parents_in_db = (
        db_session.query(File.id, File.path)
        .filter(
            File.namespace_id == namespace_id,
            File.path.in_(str(p.path.relative_to(rel_to)) for p in parents),
            File.is_dir.is_(True),
        )
        .order_by(File.path.collate("NOCASE"))
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
            # we want to commit this earlier, so other requests can see changes
            db_session.commit()
        except sqlalchemy.exc.IntegrityError as exc:
            # this folder already created by other request,
            # so just refetch the right parent
            db_session.rollback()
            parent = get_folder(
                db_session, namespace_id, storage_file.path.relative_to(rel_to),
            )
            if not parent:
                raise Exception("Failed to create parent") from exc

    return parent


def update(
    db_session: Session,
    storage_file: StorageFile,
    namespace_id: int,
    rel_to: StrOrPath,
) -> File:
    file = get(db_session, namespace_id, storage_file.path.relative_to(rel_to)),

    file.size = storage_file.size
    file.mtime = storage_file.mtime
    db_session.add(file)

    return file


def move(
    db_session: Session, namespace_id: int, from_path: StrOrPath, to_path: StrOrPath,
):
    return (
        db_session.query(File)
        .filter(File.namespace_id == namespace_id)
        .filter(
            # todo: from_path should be escaped
            (File.path == str(from_path))
            | (File.path.like(f"{from_path}/%")),
        )
        .update(
            {"path": func.replace(File.path, str(from_path), str(to_path))},
            synchronize_session=False,
        )
    )


def delete(db_session: Session, namespace_id: int, path: StrOrPath):
    return (
        db_session.query(File)
        .filter(File.namespace_id == namespace_id, File.path == str(path))
        .delete(synchronize_session=False)
    )


def empty_trash(db_session: Session, namespace_id: int):
    (
        db_session.query(File)
        .filter(
            File.namespace_id == namespace_id,
            File.path == TRASH_FOLDER_NAME,
        )
        .update({"size": 0}, synchronize_session=False)
    )
    return (
        db_session.query(File)
        .filter(
            File.namespace_id == namespace_id,
            File.path.like(f"{TRASH_FOLDER_NAME}/%"),
        )
        .delete(synchronize_session=False)
    )
