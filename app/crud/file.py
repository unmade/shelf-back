from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

import edgedb
from sqlalchemy.orm import Session

from app import errors
from app.config import TRASH_FOLDER_NAME
from app.entities import File
from app.storage import StorageFile

if TYPE_CHECKING:
    from uuid import UUID
    from edgedb import AsyncIOConnection
    from app.typedefs import StrOrPath


async def create_batch(
    conn: AsyncIOConnection,
    namespace: StrOrPath,
    path: StrOrPath,
    files: list[File],
) -> None:
    """
    Create files in a given path.

    Note, unlike 'create' this will not update parents size.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (StrOrPath): Namespace where files will be created.
        path (StrOrPath): Path to a folder where files will be created.
        files (list[File]): List of files to create. All files must have 'path'
            as a parent.

    Raises:
        errors.FileNotFound: If path to a folder does not exists.
        errors.NotADirectory: If path to a folder is not a directory.
    """
    parent = await get(conn, namespace, path)
    if not parent.is_dir:
        raise errors.NotADirectory

    query = """
        WITH
            parent := (
                SELECT
                    File
                FILTER
                    .path = <str>$parent
                    AND
                    .namespace.path = <str>$namespace
                LIMIT 1
            )
        FOR file IN {array_unpack(<array<json>>$files)}
        UNION (
            INSERT File {
                name := <str>file['name'],
                path := <str>file['path'],
                size := <int64>file['size'],
                mtime := <float64>file['mtime'],
                is_dir := <bool>file['is_dir'],
                parent := parent,
                namespace := parent.namespace,
            }
        )
    """
    await conn.query(
        query,
        namespace=str(namespace),
        parent=str(path),
        files=[file.json() for file in files],
    )


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

    If the file size is greater than zero, then size of all parents updated accordingly.

    Args:
        conn (AsyncIOConnection): Connection to a database.
        namespace (StrOrPath): Namespace path where a file should be created.
        path (StrOrPath): Path to a file to create.
        size (int, optional): File size. Defaults to 0.
        mtime (float, optional): Time of last modification. Defaults to current time.
        folder (bool, optional): Whether it is a folder or a file. Defaults to False.

    Raises:
        FileAlreadyExists: If file in a target path already exists.
        MissingParent: If target path does not have a parent.
        NotADirectory: If parent path is not a directory.
    """
    namespace = Path(namespace)
    fullpath = namespace / path
    relpath = fullpath.relative_to(namespace)
    mtime = mtime or time.time()

    if path != "." and not await exists(conn, namespace, relpath.parent, folder=True):
        raise errors.MissingParent()

    params = dict(
        name=fullpath.name,
        path=str(relpath),
        size=size,
        mtime=time.time(),
        is_dir=folder,
        namespace=str(namespace),
        parent=str(relpath.parent),
    )

    insert_query = """
        INSERT File {
            name := <str>$name,
            path := <str>$path,
            size := <int64>$size,
            mtime := <float64>$mtime,
            is_dir := <bool>$is_dir,
            parent := (
                SELECT
                    Parent
                FILTER
                    .path = <str>$parent
                    AND
                    .namespace = namespace
                    AND
                    .is_dir = true
                LIMIT 1
            ),
            namespace := namespace,
        }
    """

    update_query = ""
    if size:
        update_query = f"""
            UPDATE
                Parents
            FILTER
                .path IN {{array_unpack(<array<str>>($parents))}}
                AND
                .namespace = namespace
            SET {{
                size := .size + (SELECT ({insert_query}).size)
            }}
        """
        params["parents"] = [str(p) for p in relpath.parents]

    query = f"""
        WITH
            Parent := File,
            {'Parents := File,' if size else ''}
            namespace := (
                SELECT
                    Namespace
                FILTER
                    .path = <str>$namespace
                LIMIT 1
            )
        {update_query if size else insert_query}
    """

    try:
        await conn.query(query, **params)
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
    parents = await get_many(conn, namespace, paths)
    assert len(parents) > 0, f"No home folder in a namespace: '{namespace}'"
    if any(not p.is_dir for p in parents):
        raise errors.NotADirectory()
    if str(parents[-1].path) == str(path):
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
    """
    Delete all files and folders in the Trash.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (StrOrPath): Namespace where to empty the Trash folder.
    """
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
        FileNotFound: If file with a target path does not exists.

    Returns:
        File: File with a target path.
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


async def get_many(
    conn: AsyncIOConnection,
    namespace: StrOrPath,
    paths: Iterable[StrOrPath],
) -> list[File]:
    """
    Returns all files with target paths.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (StrOrPath): Namespace where files are located.
        paths (Iterable[StrOrPath]): Iterable of paths to look for.

    Returns:
        list[File]: Files with target paths.
    """
    query = """
        SELECT
            File {
                id, name, path, size, mtime, is_dir
            }
        FILTER
            .path IN {array_unpack(<array<str>>$paths)}
            AND
            .namespace.path = <str>$namespace
        ORDER BY
            .path ASC
    """
    files = await conn.query(
        query,
        namespace=str(namespace),
        paths=[str(p) for p in paths]
    )

    return [File.from_orm(f) for f in files]


async def list_folder(
    conn: AsyncIOConnection,
    namespace: StrOrPath, path: StrOrPath,
    with_trash: bool = False,
) -> list[File]:
    """
    Return folder contents.

    To list home folder, use '.'.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (StrOrPath): Namespace where a folder located.
        path (StrOrPath): Path to a folder in this namespace.
        with_trash (bool, optional): Whether to include Trash folder. Defaults to False.

    Raises:
        FileNotFound: If folder at this path does not exists.
        NotADirectory: If path points to a file.

    Returns:
        List[File]: List of all files/folders in a folder with a target path.
    """
    query = f"""
        SELECT File {{
            is_dir,
            children := (
                SELECT File.<parent[IS File] {{ id, name, path, size, mtime, is_dir }}
                {"FILTER .path != 'Trash'" if not with_trash and path == "." else ""}
                ORDER BY .is_dir DESC THEN .path ASC
            )
        }}
        FILTER
            .path = <str>$path
            AND
            .namespace.path = <str>$namespace
        LIMIT 1
    """
    try:
        parent = await conn.query_one(query, namespace=str(namespace), path=str(path))
    except edgedb.NoDataError as exc:
        raise errors.FileNotFound() from exc

    if not parent.is_dir:
        raise errors.NotADirectory()

    return [File.from_orm(child) for child in parent.children]


async def move(
    conn: AsyncIOConnection,
    namespace: StrOrPath,
    path: StrOrPath,
    next_path: StrOrPath,
) -> None:
    """
    Move a file or folder to a different location in the given Namespace.
    If the source path is a folder all its contents will be moved.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (StrOrPath): Namespace where a file is located.
        path (StrOrPath): Path to be moved.
        next_path (StrOrPath): Path that is the destination.

    Raises:
        errors.FileAlreadyExists: If some file already at the destination path.
        errors.FileNotFound: If source path does not exists.
        errors.MissingParent: If 'next_path' parent does not exists.
        errors.NotADirectory: If one of the 'next_path' parents is not a folder.
    """
    assert path not in (".", TRASH_FOLDER_NAME), "Can't move Home or Trash folder."
    assert not str(next_path).startswith(str(path)), "Can't move to itself."

    path = Path(path)
    next_path = Path(next_path)

    target = await get(conn, namespace, path)

    try:
        next_parent = await get(conn, namespace, next_path.parent)
    except errors.FileNotFound as exc:
        raise errors.MissingParent() from exc
    else:
        if not next_parent.is_dir:
            raise errors.NotADirectory()

    if await exists(conn, namespace, next_path):
        raise errors.FileAlreadyExists()

    await _move_file(conn, target.id, next_path)
    if target.is_dir:
        await _move_folder_content(conn, namespace, path, next_path)

    to_decrease = set(path.parents).difference(next_path.parents)
    to_increase = set(next_path.parents).difference(path.parents)

    query = """
        FOR item IN {array_unpack(<array<json>>$data)}
        UNION (
            UPDATE
                File
            FILTER
                .path IN {array_unpack(<array<str>>item['parents'])}
                AND
                .namespace.path = <str>$namespace
            SET {
                size := .size + <int64>item['size']
            }
        )
    """

    await conn.query(
        query,
        namespace=str(namespace),
        data=[
            json.dumps({
                "size": sign * target.size,
                "parents": [str(p) for p in parents]
            })
            for sign, parents in zip((-1, 1), (to_decrease, to_increase))
        ]
    )


async def _move_file(
    conn: AsyncIOConnection, file_id: UUID, next_path: StrOrPath
) -> None:
    """
    Update file name and path.

    Args:
        conn (AsyncIOConnection): Database connection.
        file_id (UUID): File ID to be updated.
        next_path (StrOrPath): New path for a file.
    """
    await conn.query("""
        UPDATE
            File
        FILTER
            .id = <uuid>$file_id
        SET {
            name := <str>$name,
            path := <str>$path,
        }
    """, file_id=str(file_id), name=next_path.name, path=str(next_path))


async def _move_folder_content(
    conn: AsyncIOConnection,
    namespace: StrOrPath,
    path: StrOrPath,
    next_path: StrOrPath,
) -> None:
    """
    Replace 'path' to 'next_path' for all files with path that starts with 'path'.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (StrOrPath): Namespace where files should be updated.
        path (StrOrPath): Path to be replace.
        next_path (StrOrPath): Path to replace.
    """
    await conn.query("""
        UPDATE
            File
        FILTER
            .path LIKE <str>$path ++ '/%'
            AND
            .namespace.path = <str>$namespace
        SET {
            path := re_replace(<str>$path, <str>$next_path, .path)
        }
    """, namespace=str(namespace), path=str(path), next_path=str(next_path))


async def next_path(
    conn: AsyncIOConnection, namespace: StrOrPath, path: StrOrPath
) -> str:
    """
    Return a path with modified name if current one already taken, otherwise return
    path unchanged.

    For example, if path 'a/f.tar.gz' exists, then next path will be 'a/f (1).tar.gz'.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (StrOrPath): Namespace to check for target path.
        path (StrOrPath): Target path.

    Returns:
        str: Path with a modified name if current one already taken, otherwise return
             path unchanged
    """
    if not await exists(conn, namespace, path):
        return path

    suffix = "".join(Path(path).suffixes)
    path_stem = str(path).rstrip(suffix)
    count = await conn.query_one("""
        SELECT count(
            File
            FILTER
                re_test(<str>$pattern, .path)
                AND
                .namespace.path = <str>$namespace
        )
    """, namespace=str(namespace), pattern=f"{path_stem} \\([[:digit:]]+\\){suffix}")
    return f"{path_stem} ({count + 1}){suffix}"


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
