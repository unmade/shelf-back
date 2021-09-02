from __future__ import annotations

import json
import time
from os.path import join as joinpath
from os.path import normpath
from pathlib import PurePath
from typing import TYPE_CHECKING, Any, Iterable, Iterator, Optional, cast

import edgedb

from app import errors, mediatypes
from app.config import TRASH_FOLDER_NAME
from app.entities import File

if TYPE_CHECKING:
    from uuid import UUID
    from app.typedefs import DBAnyConn, StrOrPath


def _lowered(items: Iterable[Any]) -> Iterator[str]:
    """Return an iterator of lower-cased strings."""
    return (str(item).lower() for item in items)


def from_db(obj: edgedb.Object) -> File:
    return File.construct(
        id=obj.id,
        name=obj.name,
        path=obj.path,
        size=obj.size,
        mtime=obj.mtime,
        mediatype=obj.mediatype.name,
    )


async def create(
    conn: DBAnyConn,
    namespace: StrOrPath,
    path: StrOrPath,
    *,
    size: int = 0,
    mtime: float = None,
    mediatype: str = mediatypes.OCTET_STREAM,
) -> File:
    """
    Create a new file.

    If the file size is greater than zero, then size of all parents updated accordingly.

    Args:
        conn (DBAnyConn): Connection to a database.
        namespace (StrOrPath): Namespace path where a file should be created.
        path (StrOrPath): Path to a file to create.
        size (int, optional): File size. Defaults to 0.
        mtime (float, optional): Time of last modification. Defaults to current time.
        mediatype (str, optional): Media type. Defaults to 'application/octet-stream'.

    Raises:
        FileAlreadyExists: If file in a target path already exists.
        MissingParent: If target path does not have a parent.
        NotADirectory: If parent path is not a directory.

    Returns:
        File: Created file.
    """
    namespace = PurePath(namespace)
    path = PurePath(path)
    mtime = mtime or time.time()

    try:
        parent = await get(conn, namespace, path.parent)
    except errors.FileNotFound as exc:
        raise errors.MissingParent() from exc
    else:
        if not parent.is_folder():
            raise errors.NotADirectory()

    query = """
        SELECT (
            INSERT File {
                name := <str>$name,
                path := <str>$path,
                size := <int64>$size,
                mtime := <float64>$mtime,
                mediatype := (
                    INSERT MediaType {
                        name := <str>$mediatype
                    }
                    UNLESS CONFLICT ON .name
                    ELSE (
                        SELECT
                            MediaType
                        FILTER
                            .name = <str>$mediatype
                    )
                ),
                namespace := (
                    SELECT
                        Namespace
                    FILTER
                        .path = <str>$namespace
                    LIMIT 1
                ),
            }
        ) { id, name, path, size, mtime, mediatype: { name } }
    """

    params = {
        "name": (namespace / path).name,
        "path": normpath(joinpath(parent.path, path.name)) if parent else ".",
        "size": size,
        "mtime": mtime,
        "mediatype": mediatype,
        "namespace": str(namespace),
    }

    try:
        file = await conn.query_single(query, **params)
    except edgedb.ConstraintViolationError as exc:
        raise errors.FileAlreadyExists() from exc

    if size:
        await inc_size_batch(conn, namespace, path.parents, size)

    return from_db(file)


async def create_batch(
    conn: DBAnyConn, namespace: StrOrPath, files: Iterable[Optional[File]],
) -> None:
    """
    Create files at once.

    CAUTION:
        - method doesn't update size of the parents
        - method doesn't restore original casing
        - method doesn't enforce parent path existence

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Namespace where files will be created.
        files (Iterable[Optional[File]]): Iterable of files to create.

    Raises:
        errors.FileAlreadyExists: If some file already exists.
    """

    query = """
        WITH
            files := array_unpack(<array<json>>$files),
            namespace := (
                SELECT
                    Namespace
                FILTER
                    .path = <str>$namespace
                LIMIT 1
            ),
            mediatypes := (
                FOR mediatype IN {DISTINCT files['mediatype']}
                UNION (
                    INSERT MediaType {
                        name := <str>mediatype
                    }
                    UNLESS CONFLICT ON .name
                    ELSE (
                        SELECT MediaType
                    )
                )
            ),
        FOR file IN {files}
        UNION (
            INSERT File {
                name := <str>file['name'],
                path := <str>file['path'],
                size := <int64>file['size'],
                mtime := <float64>file['mtime'],
                mediatype := (
                    SELECT
                        mediatypes
                    FILTER
                        .name = <str>file['mediatype']
                ),
                namespace := namespace,
            }
        )
    """

    params = {
        "namespace": str(namespace),
        "files": [file.json() for file in files if file is not None],
    }

    if not params["files"]:
        return

    try:
        await conn.query(query, **params)
    except edgedb.ConstraintViolationError as exc:
        raise errors.FileAlreadyExists() from exc


async def create_folder(conn: DBAnyConn, namespace: StrOrPath, path: StrOrPath) -> None:
    """
    Create a folder with any missing parents of the target path.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Namespace where to create folder to.
        path (StrOrPath): Path in the namespace to create the folder.

    Raises:
        FileAlreadyExists: If folder at target path already exists.
        NotADirectory: If one of the parents is not a directory.
    """
    paths = [str(path)] + [str(p) for p in PurePath(path).parents]

    parents = await get_many(conn, namespace, paths)
    assert len(parents) > 0, f"No home folder in a namespace: '{namespace}'"

    if any(not p.is_folder() for p in parents):
        raise errors.NotADirectory()
    if parents[-1].path.lower() == str(path).lower():
        raise errors.FileAlreadyExists()

    paths_lower = [p.lower() for p in paths]
    index = paths_lower.index(parents[-1].path.lower())

    for p in reversed(paths[:index]):
        try:
            await create(conn, namespace, p, mediatype=mediatypes.FOLDER)
        except (errors.FileAlreadyExists, errors.MissingParent):
            pass


async def create_home_folder(conn: DBAnyConn, namespace: StrOrPath) -> File:
    """
    Create a home folder.

    Args:
        conn (DBAnyConn): Connection to a database.
        namespace (StrOrPath): Namespace path where a file should be created.

    Raises:
        FileAlreadyExists: If file in a target path already exists.

    Returns:
        File: A freshly created home folder.
    """
    namespace = PurePath(namespace)

    query = """
        SELECT (
            INSERT File {
                name := <str>$name,
                path := <str>$path,
                size := 0,
                mtime := <float64>$mtime,
                mediatype := (
                    INSERT MediaType {
                        name := <str>$mediatype
                    }
                    UNLESS CONFLICT ON .name
                    ELSE (
                        SELECT
                            MediaType
                        FILTER
                            .name = <str>$mediatype
                    )
                ),
                namespace := (
                    SELECT
                        Namespace
                    FILTER
                        .path = <str>$namespace
                    LIMIT 1
                ),
            }
        ) { id, name, path, size, mtime, mediatype: { name } }
    """

    try:
        file = await conn.query_single(
            query,
            name=namespace.name,
            path=".",
            mtime=time.time(),
            mediatype=mediatypes.FOLDER,
            namespace=str(namespace),
        )
    except edgedb.ConstraintViolationError as exc:
        raise errors.FileAlreadyExists() from exc

    return from_db(file)


async def delete(conn: DBAnyConn, namespace: StrOrPath, path: StrOrPath) -> File:
    """
    Permanently delete file or a folder with all of its contents and decrease size
    of the parents accordingly.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Namespace where to delete a file.
        path (StrOrPath): Path to a file.

    Raises:
        FileNotFound: If file/folder with a given path does not exists.

    Returns:
        File: Deleted file.
    """

    query = """
        SELECT (
            DELETE
                File
            FILTER
                .namespace.path = <str>$namespace
                AND (
                    str_lower(.path) = str_lower(<str>$path)
                    OR
                    str_lower(.path) LIKE str_lower(<str>$path) ++ '/%'
                )
        ) { id, name, path, size, mtime, mediatype: { name } }
    """

    try:
        file = from_db(
            (await conn.query(query, namespace=str(namespace), path=str(path)))[0]
        )
    except IndexError as exc:
        raise errors.FileNotFound() from exc

    await inc_size_batch(conn, namespace, PurePath(path).parents, size=-file.size)

    return file


async def delete_batch(
    conn: DBAnyConn, namespace: StrOrPath, path: StrOrPath, names: Iterable[str],
) -> None:
    """
    Delete all files with target names in specified path and updates parents size.

    Note, that 'names' are case-sensitive.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Namespace where to delete files.
        path (StrOrPath): Path where to delete files.
        names (Iterable[str]): File names to delete.
    """
    if not names:
        return

    query = """
        SELECT sum((
            DELETE
                File
            FILTER
                .namespace.path = <str>$namespace
                AND
                .name IN {array_unpack(<array<str>>$names)}
        ).size)
    """
    size = await conn.query_single(query, namespace=str(namespace), names=list(names))
    parents = [path] + [p for p in PurePath(path).parents]
    await inc_size_batch(conn, namespace, parents, size=-size)


async def empty_trash(conn: DBAnyConn, namespace: StrOrPath) -> File:
    """
    Delete all files and folders in the Trash.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Namespace where to empty the Trash folder.

    Returns:
        File: Trash folder.
    """
    trash = await get(conn, namespace, TRASH_FOLDER_NAME)
    await conn.query("""
        DELETE
            File
        FILTER
            str_lower(.path) LIKE str_lower(<str>$path) ++ '/%'
            AND
            .namespace.path = <str>$namespace
    """, namespace=str(namespace), path=TRASH_FOLDER_NAME)
    paths = [".", TRASH_FOLDER_NAME]
    await inc_size_batch(conn, str(namespace), paths=paths, size=-trash.size)

    trash.size = 0
    return trash


async def exists(conn: DBAnyConn, namespace: StrOrPath, path: StrOrPath) -> bool:
    """
    Check whether a file or a folder exists in a target path.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Namespace where to look for a path.
        path (StrOrPath): Path to a file or a folder.

    Returns:
        bool: True if file/folder exists, False otherwise.
    """
    query = """
        SELECT EXISTS (
            SELECT
                File
            FILTER
                str_lower(.path) = str_lower(<str>$path)
                AND
                .namespace.path = <str>$namespace
        )
    """

    return cast(
        bool,
        await conn.query_single(query, namespace=str(namespace), path=str(path)),
    )


async def get(conn: DBAnyConn, namespace: StrOrPath, path: StrOrPath) -> File:
    """
    Return file with a target path.

    Args:
        conn (DBAnyConn): Database connection.
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
                id, name, path, size, mtime, mediatype: { name }
            }
        FILTER
            str_lower(.path) = str_lower(<str>$path)
            AND
            .namespace.path = <str>$namespace
    """
    try:
        return from_db(
            await conn.query_single(query, namespace=str(namespace), path=str(path))
        )
    except edgedb.NoDataError as exc:
        raise errors.FileNotFound() from exc


async def get_many(
    conn: DBAnyConn, namespace: StrOrPath, paths: Iterable[StrOrPath],
) -> list[File]:
    """
    Return all files with target paths.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Namespace where files are located.
        paths (Iterable[StrOrPath]): Iterable of paths to look for.

    Returns:
        List[File]: Files with target paths.
    """
    query = """
        SELECT
            File {
                id, name, path, size, mtime, mediatype: { name },
            }
        FILTER
            str_lower(.path) IN {array_unpack(<array<str>>$paths)}
            AND
            .namespace.path = <str>$namespace
        ORDER BY
            str_lower(.path) ASC
    """
    files = await conn.query(
        query,
        namespace=str(namespace),
        paths=[str(p).lower() for p in paths]
    )

    return [from_db(f) for f in files]


async def list_folder(
    conn: DBAnyConn,
    namespace: StrOrPath,
    path: StrOrPath,
    *,
    with_trash: bool = False,
) -> list[File]:
    """
    Return folder contents.

    To list home folder, use '.'.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Namespace where a folder located.
        path (StrOrPath): Path to a folder in this namespace.
        with_trash (bool, optional): Whether to include Trash folder. Defaults to False.

    Raises:
        FileNotFound: If folder at this path does not exists.
        NotADirectory: If path points to a file.

    Returns:
        List[File]: List of all files/folders in a folder with a target path.
    """
    path = str(path)

    parent = await get(conn, namespace, path)
    if not parent.mediatype == mediatypes.FOLDER:
        raise errors.NotADirectory()

    filter_clause = ""
    if path == ".":
        filter_clause = "AND .path != '.'"
        if not with_trash:
            filter_clause += " AND .path != 'Trash'"

    query = f"""
        SELECT
            File {{
                id, name, path, size, mtime, mediatype: {{ name }},
            }}
        FILTER
            .namespace.path = <str>$namespace
            AND
            .path LIKE <str>$path ++ '%'
            AND
            .path NOT LIKE <str>$path ++ '%/%'
            {filter_clause}
        ORDER BY
            .mediatype.name = '{mediatypes.FOLDER}' DESC
        THEN
            str_lower(.path) ASC
    """

    path = "" if path == "." else f"{path}/"
    files = await conn.query(query, namespace=str(namespace), path=path)
    return [from_db(file) for file in files]


async def move(
    conn: DBAnyConn,
    namespace: StrOrPath,
    path: StrOrPath,
    next_path: StrOrPath,
) -> File:
    """
    Move a file or folder to a different location in the target Namespace.
    If the source path is a folder all its contents will be moved.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Namespace where a file is located.
        path (StrOrPath): Path to be moved.
        next_path (StrOrPath): Path that is the destination.

    Raises:
        errors.FileAlreadyExists: If some file already at the destination path.
        errors.FileNotFound: If source or destination path does not exists.
        errors.NotADirectory: If one of the 'next_path' parents is not a folder.

    Returns:
        File: Moved file.
    """
    path = PurePath(path)
    next_path = PurePath(next_path)

    # this call also ensures path exists
    target = await get(conn, namespace, path)

    next_parent = await get(conn, namespace, next_path.parent)
    if not next_parent.is_folder():
        raise errors.NotADirectory()

    # restore original parent casing
    next_path = PurePath(next_parent.path) / next_path.name
    if await exists(conn, namespace, next_path):
        raise errors.FileAlreadyExists()

    to_decrease = set(_lowered(path.parents)).difference(_lowered(next_path.parents))
    to_increase = set(_lowered(next_path.parents)).difference(_lowered(path.parents))

    query = """
        FOR item IN {array_unpack(<array<json>>$data)}
        UNION (
            UPDATE
                File
            FILTER
                str_lower(.path) IN {array_unpack(<array<str>>item['parents'])}
                AND
                .namespace.path = <str>$namespace
            SET {
                size := .size + <int64>item['size']
            }
        )
    """

    file = await _move_file(conn, target.id, next_path)
    if target.is_folder():
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


async def _move_file(conn: DBAnyConn, file_id: UUID, next_path: StrOrPath) -> File:
    """
    Update file name and path.

    Args:
        conn (DBAnyConn): Database connection.
        file_id (UUID): File ID to be updated.
        next_path (StrOrPath): New path for a file.

    Returns:
        File: Updated file.
    """
    query = """
        SELECT (
            UPDATE
                File
            FILTER
                .id = <uuid>$file_id
            SET {
                name := <str>$name,
                path := <str>$path,
            }
        ) { id, name, path, size, mtime, mediatype: { name } }
    """
    return from_db(
        await conn.query_single(
            query,
            file_id=str(file_id),
            name=PurePath(next_path).name,
            path=str(next_path),
        )
    )


async def _move_folder_content(
    conn: DBAnyConn,
    namespace: StrOrPath,
    path: StrOrPath,
    next_path: StrOrPath,
) -> None:
    """
    Replace 'path' to 'next_path' for all files with path that starts with 'path'.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Namespace where files should be updated.
        path (StrOrPath): Path to be replace.
        next_path (StrOrPath): Path to replace.
    """
    await conn.query("""
        UPDATE
            File
        FILTER
            str_lower(.path) LIKE str_lower(<str>$path) ++ '/%'
            AND
            .namespace.path = <str>$namespace
        SET {
            path := re_replace(str_lower(<str>$path), <str>$next_path, str_lower(.path))
        }
    """, namespace=str(namespace), path=str(path), next_path=str(next_path))


async def next_path(conn: DBAnyConn, namespace: StrOrPath, path: StrOrPath) -> str:
    """
    Return a path with modified name if current one already taken, otherwise return
    path unchanged.

    For example, if path 'a/f.tar.gz' exists, then next path will be 'a/f (1).tar.gz'.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Namespace to check for target path.
        path (StrOrPath): Target path.

    Returns:
        str: Path with a modified name if current one already taken, otherwise return
             path unchanged
    """
    if not await exists(conn, namespace, path):
        return str(path)

    suffix = "".join(PurePath(path).suffixes)
    path_stem = str(path).rstrip(suffix)
    count = await conn.query_single("""
        SELECT count(
            File
            FILTER
                re_test(str_lower(<str>$pattern), str_lower(.path))
                AND
                .namespace.path = <str>$namespace
        )
    """, namespace=str(namespace), pattern=f"{path_stem} \\([[:digit:]]+\\){suffix}")
    return f"{path_stem} ({count + 1}){suffix}"


async def inc_size_batch(
    conn: DBAnyConn,
    namespace: StrOrPath,
    paths: Iterable[StrOrPath],
    size: int,
) -> None:
    """
    Increments size for specified paths.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Namespace.
        paths (Iterable[StrOrPath]): List of path which size will be incremented.
        size (int): value that will be added to the current file size.
    """
    if not size:
        return

    await conn.query("""
        UPDATE
            File
        FILTER
            str_lower(.path) IN array_unpack(<array<str>>$paths)
            AND
            .namespace.path = <str>$namespace
        SET {
            size := .size + <int64>$size
        }
    """, namespace=str(namespace), paths=[str(p).lower() for p in paths], size=size)
