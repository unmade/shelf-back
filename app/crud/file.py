from __future__ import annotations

import operator
import time
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

import edgedb
import sqlalchemy.exc
from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from app import errors
from app.config import TRASH_FOLDER_NAME
from app.models import File
from app.storage import StorageFile

if TYPE_CHECKING:
    from edgedb import AsyncIOConnection
    from app.typedefs import StrOrPath


async def create(
    conn: AsyncIOConnection,
    namespace: StrOrPath,
    path: StrOrPath,
    size: int = 0,
    mtime: float = None,
    folder: bool = False,
) -> None:
    """
    Create new file.

    Args:
        conn (AsyncIOConnection): Connection to a database.
        namespace (StrOrPath): Namespace path where a file should be created.
        path (StrOrPath): Path to a file to create.
        size (int, optional): File size. Defaults to 0.
        mtime (float, optional): Time of last modification. Defaults to current time.
        folder (bool, optional): Whether it is a folder or a file. Defaults to False.

    Raises:
        FileAlreadyExists: If file in a target path already exists
        MissingParent: If target path does not have a parent.
        NotADirectory: If parent path is not a directory.
    """
    namespace = Path(namespace)
    fullpath = namespace / path
    relpath = fullpath.relative_to(namespace)
    mtime = mtime or time.time()

    if path != "." and not await exists(conn, namespace, relpath.parent, folder=True):
        raise errors.MissingParent()

    query = """
        WITH
            Parent := File,
            namespace := (
                SELECT Namespace
                FILTER
                    .path = <str>$namespace
                LIMIT 1
            ),
            parent := (
                SELECT Parent
                FILTER
                    .path = <str>$parent
                    AND
                    .namespace = namespace
                    AND
                    .is_dir = true
                LIMIT 1
            )
        INSERT File {
            name := <str>$name,
            path := <str>$path,
            size := <int64>$size,
            mtime := <float64>$mtime,
            is_dir := <bool>$is_dir,
            parent := parent,
            namespace := namespace,
        }
    """

    try:
        await conn.query_one(
            query,
            name=fullpath.name,
            path=str(relpath),
            size=size,
            mtime=time.time(),
            is_dir=folder,
            namespace=str(namespace),
            parent=str(relpath.parent),
        )
    except edgedb.ConstraintViolationError as exc:
        raise errors.FileAlreadyExists from exc


async def create_folder(
    conn: AsyncIOConnection, namespace: StrOrPath, path: StrOrPath,
) -> None:
    """
    Create a folder with any missing parents of the target path.

    If target path already exists, do nothing.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (StrOrPath): Namespace where to create folder to.
        path (StrOrPath): Path in the namespace to create the folder.

    Raises:
        FileAlreadyExists: If folder at target path already exists.
        NotADirectory: If one of the parents is not a directory.
    """
    paths = [str(path)] + [str(p) for p in Path(path).parents]
    query = """
        SELECT File { id, path, is_dir }
        FILTER
            .path IN {array_unpack(<array<str>>$paths)}
            AND
            .namespace.path = <str>$namespace
        ORDER BY .path ASC
    """
    parents = await conn.query(query, namespace=str(namespace), paths=paths)
    assert len(parents) > 0, f"No home folder in a namespace {namespace}"
    if any(not p.is_dir for p in parents):
        raise errors.NotADirectory()
    if parents[-1].path == str(path):
        raise errors.FileAlreadyExists()

    to_create = list(reversed(paths[:paths.index(parents[-1].path)]))

    for p in to_create:
        try:
            await create(conn, namespace, p, folder=True)
        except (errors.FileAlreadyExists, errors.MissingParent):
            pass


async def delete(
    conn: AsyncIOConnection, namespace: StrOrPath, path: StrOrPath,
) -> None:
    """
    Permanently delete file or a folder with all of its contents and decrease size
    of the parents folders decreases accordingly.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (StrOrPath): Namespace where to delete a file.
        path (StrOrPath): Path to a file.
    """
    query = """
        WITH
            Parent := File,
            namespace := (
                SELECT Namespace
                FILTER
                    .path = <str>$namespace
                LIMIT 1
            )
        UPDATE Parent
        FILTER
            namespace = namespace
            AND
            .path IN {array_unpack(<array<str>>$parents)}
        SET {
            size := .size - (
                SELECT (
                    DELETE File
                    FILTER
                        namespace = namespace
                        AND
                        .path = <str>$path
                ) { size }
            ).size
        }
    """
    await conn.query(
        query,
        namespace=str(namespace),
        path=str(path),
        parents=[str(p) for p in Path(path).parents],
    )


async def empty_trash(conn: AsyncIOConnection, namespace: StrOrPath) -> None:
    # todo: try to make it atomic with one query
    async with conn.transaction():
        await conn.query("""
            DELETE File
                FILTER
                    .path LIKE <str>$path ++ '/%'
                    AND
                    .namespace.path = <str>$namespace
        """, namespace=str(namespace), path=TRASH_FOLDER_NAME)
        await conn.query("""
            UPDATE File
            FILTER
                .path = <str>$path
                AND
                .namespace.path = <str>$namespace
            SET {
                size := 0
            }
        """, namespace=str(namespace), path=TRASH_FOLDER_NAME)


async def exists(
    conn: AsyncIOConnection, namespace: StrOrPath, path: StrOrPath, folder: bool = None,
) -> bool:
    """
    Checks whether a file or a folder exists in a given path.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (StrOrPath): Namespace where to look for a path.
        path (StrOrPath): Path to a file or a folder.
        folder (bool, optional): If True, will check only if folder exists, otherwise
            will check for a file. If None (default) will check for both.

    Returns:
        bool: True if file/folder exists, False otherwise.
    """
    query = f"""
        SELECT EXISTS (
            SELECT File
            FILTER
                .path = <str>$path
                AND
                .namespace.path = <str>$namespace
                {"AND .is_dir = <bool>$is_dir" if folder is not None else ""}
        )
    """

    params = {
        "namespace": str(namespace),
        "path": str(path),
    }
    if folder is not None:
        params["is_dir"] = folder

    return await conn.query_one(query, **params)


async def get(conn: AsyncIOConnection, namespace: StrOrPath, path: StrOrPath) -> File:
    """
    Returns file with a target path.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (StrOrPath): Namespace where to look for a file.
        path (StrOrPath): Path to a file.

    Raises:
        FileNotFound: If file with a target does not exists.

    Returns:
        File:
    """
    query = """
        SELECT File { id, name, path, size, mtime, is_dir }
        FILTER
            .path = <str>$path
            AND
            .namespace.path = <str>$namespace
    """
    try:
        return await conn.query_one(query, namespace=str(namespace), path=str(path))
    except edgedb.NoDataError as exc:
        raise errors.FileNotFound() from exc


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
        try:
            parent = create(
                db_session,
                storage_file,
                namespace_id,
                rel_to=rel_to,
                parent_id=parent.id,
            )
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
    file = get(db_session, namespace_id, storage_file.path.relative_to(rel_to))

    file.size = storage_file.size
    file.mtime = storage_file.mtime
    db_session.add(file)
    db_session.flush()

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
