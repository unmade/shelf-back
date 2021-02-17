from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

import edgedb

from app import errors
from app.config import TRASH_FOLDER_NAME
from app.entities import File

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
        errors.FileAlreadyExists: If some file already exists.
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
    try:
        await conn.query(
            query,
            namespace=str(namespace),
            parent=str(path),
            files=[file.json() for file in files],
        )
    except edgedb.ConstraintViolationError as exc:
        raise errors.FileAlreadyExists() from exc


async def create(
    conn: AsyncIOConnection,
    namespace: StrOrPath,
    path: StrOrPath,
    *,
    size: int = 0,
    mtime: float = None,
    is_dir: bool = False,
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
        is_dir (bool, optional): Whether it is a folder or a file. Defaults to False.

    Raises:
        FileAlreadyExists: If file in a target path already exists.
        MissingParent: If target path does not have a parent.
        NotADirectory: If parent path is not a directory.

    Returns:
        File: Created file.
    """
    namespace = Path(namespace)
    path = Path(path)
    mtime = mtime or time.time()

    try:
        parent = await get(conn, namespace, path.parent)
    except errors.FileNotFound as exc:
        raise errors.MissingParent() from exc
    else:
        if not parent.is_dir:
            raise errors.NotADirectory

    query = """
        WITH
            Parent := File,
            parent := (
                SELECT
                    Parent
                FILTER
                    .path = <str>$parent
                    AND
                    .namespace.path = <str>$namespace
                    AND
                    .is_dir = true
                LIMIT 1
            )
        SELECT (
            INSERT File {
                name := <str>$name,
                path := <str>$path,
                size := <int64>$size,
                mtime := <float64>$mtime,
                is_dir := <bool>$is_dir,
                parent := parent,
                namespace := parent.namespace,
            }
        ) { id, name, path, size, mtime, is_dir }
    """

    insert_coro = conn.query_one(
        query,
        name=(namespace / path).name,
        path=str(path),
        size=size,
        mtime=time.time(),
        is_dir=is_dir,
        namespace=str(namespace),
        parent=str(path.parent),
    )

    try:
        if size:
            async with conn.transaction():
                file = await insert_coro
                await _inc_size(conn, namespace, path.parents, size)
        else:
            file = await insert_coro
    except edgedb.ConstraintViolationError as exc:
        raise errors.FileAlreadyExists() from exc

    return File.from_orm(file)


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
            await create(conn, namespace, p, is_dir=True)
        except (errors.FileAlreadyExists, errors.MissingParent):
            pass


async def delete(
    conn: AsyncIOConnection, namespace: StrOrPath, path: StrOrPath,
) -> File:
    """
    Permanently delete file or a folder with all of its contents and decrease size
    of the parents accordingly.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (StrOrPath): Namespace where to delete a file.
        path (StrOrPath): Path to a file.

    Raises:
        FileNotFound: If file/folder with a given path does not exists.

    Returns:
        File: Deleted file.
    """

    file = await get(conn, namespace, path)

    query = """
        WITH
            Parent := File,
            namespace := (
                SELECT
                    Namespace
                FILTER
                    .path = <str>$namespace
                LIMIT 1
            )
        UPDATE Parent
        FILTER
            namespace = namespace
            AND
            .path IN array_unpack(<array<str>>$parents)
        SET {
            size := .size - (
                DELETE
                    File
                FILTER
                    namespace = namespace
                    AND
                    .path = <str>$path
            ).size
        }
    """
    await conn.query(
        query,
        namespace=str(namespace),
        path=str(path),
        parents=[str(p) for p in Path(path).parents],
    )

    return file


async def empty_trash(conn: AsyncIOConnection, namespace: StrOrPath) -> File:
    """
    Delete all files and folders in the Trash.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (StrOrPath): Namespace where to empty the Trash folder.

    Returns:
        File: Trash folder.
    """
    trash = await get(conn, namespace, TRASH_FOLDER_NAME)
    async with conn.transaction():
        await conn.query("""
            DELETE
                File
            FILTER
                .path LIKE <str>$path ++ '/%'
                AND
                .namespace.path = <str>$namespace
        """, namespace=str(namespace), path=TRASH_FOLDER_NAME)
        paths = [".", TRASH_FOLDER_NAME]
        await _inc_size(conn, str(namespace), paths=paths, size=-trash.size)

    trash.size = 0
    return trash


async def exists(
    conn: AsyncIOConnection,
    namespace: StrOrPath,
    path: StrOrPath,
    *,
    is_dir: bool = None,
) -> bool:
    """
    Check whether a file or a folder exists in a target path.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (StrOrPath): Namespace where to look for a path.
        path (StrOrPath): Path to a file or a folder.
        is_dir (bool, optional): If True, will check only if folder exists, otherwise
            will check for a file. If None (default) will check for both.

    Returns:
        bool: True if file/folder exists, False otherwise.
    """
    query = f"""
        SELECT EXISTS (
            SELECT
                File
            FILTER
                .path = <str>$path
                AND
                .namespace.path = <str>$namespace
                {"AND .is_dir = <bool>$is_dir" if is_dir is not None else ""}
        )
    """

    params = {
        "namespace": str(namespace),
        "path": str(path),
    }
    if is_dir is not None:
        params["is_dir"] = is_dir

    return await conn.query_one(query, **params)


async def get(conn: AsyncIOConnection, namespace: StrOrPath, path: StrOrPath) -> File:
    """
    Return file with a target path.

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
        SELECT
            File {
                id, name, path, size, mtime, is_dir
            }
        FILTER
            .path = <str>$path
            AND
            .namespace.path = <str>$namespace
    """
    try:
        return File.from_orm(
            await conn.query_one(query, namespace=str(namespace), path=str(path))
        )
    except edgedb.NoDataError as exc:
        raise errors.FileNotFound() from exc


async def get_many(
    conn: AsyncIOConnection,
    namespace: StrOrPath,
    paths: Iterable[StrOrPath],
) -> list[File]:
    """
    Return all files with target paths.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (StrOrPath): Namespace where files are located.
        paths (Iterable[StrOrPath]): Iterable of paths to look for.

    Returns:
        List[File]: Files with target paths.
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
    *,
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
    filter_clause = "FILTER .path != 'Trash'" if not with_trash and path == "." else ""
    query = f"""
        SELECT
            File {{
                is_dir,
                children := (
                    SELECT
                        .<parent[IS File] {{
                            id, name, path, size, mtime, is_dir
                        }}
                    {filter_clause}
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
) -> File:
    """
    Move a file or folder to a different location in the target Namespace.
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

    Returns:
        File: Moved file.
    """
    assert path not in (".", TRASH_FOLDER_NAME), "Can't move Home or Trash folder."
    assert not str(next_path).startswith(str(path)), "Can't move to itself."

    path = Path(path)
    next_path = Path(next_path)

    # this call also ensures path exists
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

    async with conn.transaction():
        file = await _move_file(conn, target.id, next_path)
        if target.is_dir:
            await _move_folder_content(conn, namespace, path, next_path)

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

    return file


async def _move_file(
    conn: AsyncIOConnection, file_id: UUID, next_path: StrOrPath
) -> File:
    """
    Update file name and path.

    Args:
        conn (AsyncIOConnection): Database connection.
        file_id (UUID): File ID to be updated.
        next_path (StrOrPath): New path for a file.

    Returns:
        File: Updated file.
    """
    return File.from_orm(
        await conn.query_one("""
            SELECT (
                UPDATE
                    File
                FILTER
                    .id = <uuid>$file_id
                SET {
                    name := <str>$name,
                    path := <str>$path,
                }
            ) { id, name, path, size, mtime, is_dir }
        """, file_id=str(file_id), name=Path(next_path).name, path=str(next_path))
    )


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


async def _inc_size(
    conn: AsyncIOConnection,
    namespace: StrOrPath,
    paths: Iterable[StrOrPath],
    size: int,
) -> None:
    """
    Increments size for specified paths.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (StrOrPath): Namespace.
        paths (Iterable[StrOrPath]): List of path which size will be incremented.
        size (int): value that will be added to the current file size.
    """
    await conn.query("""
        FOR path IN {array_unpack(<array<str>>$paths)}
        UNION (
            UPDATE
                File
            FILTER
                .path = path
                AND
                .namespace.path = <str>$namespace
            SET {
                size := .size + <int64>$size
            }
        )
    """, namespace=str(namespace), paths=[str(p) for p in paths], size=size)
