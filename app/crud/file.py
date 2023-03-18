from __future__ import annotations

import contextlib
import time
from os.path import join as joinpath
from os.path import normpath
from pathlib import PurePath
from typing import TYPE_CHECKING, Iterable, cast

import edgedb

from app import errors, mediatypes
from app.entities import File

if TYPE_CHECKING:
    from app.typedefs import DBAnyConn, StrOrPath, StrOrUUID


def from_db(obj: edgedb.Object) -> File:
    return File(
        id=str(obj.id),
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

    parent = None
    if str(path) != ".":
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
        file = await conn.query_required_single(query, **params)
    except edgedb.ConstraintViolationError as exc:
        raise errors.FileAlreadyExists() from exc

    if size:
        await inc_size_batch(conn, namespace, path.parents, size)

    return from_db(file)


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
        with contextlib.suppress(errors.FileAlreadyExists, errors.MissingParent):
            await create(conn, namespace, p, mediatype=mediatypes.FOLDER)


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
    ns_path = str(namespace)

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
        await conn.query_required_single(query, namespace=ns_path, path=str(path)),
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
        LIMIT 1
    """
    try:
        return from_db(
            await conn.query_required_single(
                query, namespace=str(namespace), path=str(path)
            )
        )
    except edgedb.NoDataError as exc:
        raise errors.FileNotFound() from exc


async def get_by_id(conn: DBAnyConn, file_id: StrOrUUID) -> File:
    """
    Return a file by ID.

    Args:
        conn (DBAnyConn): Database connection.
        file_id (StrOrUUID): File ID.

    Raises:
        errors.FileNotFound: If file with a given ID does not exists.

    Returns:
        File: File with a target ID.
    """
    query = """
        SELECT
            File {
                id, name, path, size, mtime, mediatype: { name }
            }
        FILTER
            .id = <uuid>$file_id
    """
    try:
        return from_db(
            await conn.query_required_single(query, file_id=file_id)
        )
    except edgedb.NoDataError as exc:
        raise errors.FileNotFound() from exc


async def get_by_id_batch(
    conn: DBAnyConn, namespace: StrOrPath, ids: Iterable[StrOrUUID],
) -> list[File]:
    """
    Return all files with target IDs.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Namespace where files are located.
        ids (Iterable[StrOrUUID]): Iterable of paths to look for.

    Returns:
        List[File]: Files with target IDs.
    """
    query = """
        SELECT
            File {
                id, name, path, size, mtime, mediatype: { name },
            }
        FILTER
            .id IN {array_unpack(<array<uuid>>$ids)}
            AND
            .namespace.path = <str>$namespace
        ORDER BY
            str_lower(.path) ASC
    """
    files = await conn.query(
        query,
        namespace=str(namespace),
        ids=list(ids),
    )

    return [from_db(f) for f in files]


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
