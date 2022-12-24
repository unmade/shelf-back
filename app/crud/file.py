from __future__ import annotations

import json
import time
from os.path import join as joinpath
from os.path import normpath
from pathlib import PurePath
from typing import TYPE_CHECKING, Any, AsyncIterator, Iterable, Iterator, cast

import edgedb

from app import errors, mediatypes
from app.config import TRASH_FOLDER_NAME
from app.entities import File

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.typedefs import DBAnyConn, StrOrPath, StrOrUUID


def _lowered(items: Iterable[Any]) -> Iterator[str]:
    """Return an iterator of lower-cased strings."""
    return (str(item).lower() for item in items)


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


async def create_batch(
    conn: DBAnyConn, namespace: StrOrPath, files: Iterable[File | None],
) -> None:
    """
    Create files at once.

    CAUTION:
        - method doesn't update size of the parents
        - method doesn't restore original casing
        - method doesn't enforce parent path existence
        - method doesn't create corresponding MediaTypes

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Namespace where files will be created.
        files (Iterable[File | None]): Iterable of files to create.

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
        FOR file IN {files}
        UNION (
            INSERT File {
                name := <str>file['name'],
                path := <str>file['path'],
                size := <int64>file['size'],
                mtime := <float64>file['mtime'],
                mediatype := (
                    SELECT
                        MediaType
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
        file = await conn.query_required_single(
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


async def delete_all(conn: DBAnyConn, namespace: StrOrPath) -> None:
    """
    Delete all files in a given namespace.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Namespace to reset.
    """
    query = """
        DELETE
            File
        FILTER
            .namespace.path = <str>$namespace
    """

    await conn.query(query, namespace=str(namespace))


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


async def iter_by_mediatypes(
    conn: DBAnyConn,
    namespace: StrOrPath,
    mediatypes: Sequence[str],
    *,
    batch_size: int = 25,
) -> AsyncIterator[list[File]]:
    """
    Iterate through files with a given mediatypes in batches.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Target namespace where files should be listed.
        mediatypes (Iterable[str]): List of mediatypes that files should match.
        size (int, optional): Batch size. Defaults to 25.

    Returns:
        AsyncIterator[list[File]]: None.

    Yields:
        Iterator[AsyncIterator[list[File]]]: Batch with files with a given mediatypes.
    """
    limit = batch_size
    offset = -limit

    while True:
        offset += limit
        files = await list_by_mediatypes(
            conn, namespace, mediatypes, offset=offset, limit=limit
        )
        if not files:
            return
        yield files


async def list_by_mediatypes(
    conn: DBAnyConn,
    namespace: StrOrPath,
    mediatypes: Sequence[str],
    *,
    offset: int,
    limit: int = 25,
) -> list[File]:
    """
    List all files with a given mediatypes.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Target namespace where files should be listed.
        mediatypes (Iterable[str]): List of mediatypes that files should match.
        offset (int): Skip this number of elements.
        limit (int, optional): Include only the first element-count elements.

    Returns:
        list[File]: list of Files
    """
    query = """
        SELECT
            File {
                id, name, path, size, mtime, mediatype: { name },
            }
        FILTER
            .namespace.path = <str>$namespace
            AND
            .mediatype.name IN {array_unpack(<array<str>>$mediatypes)}
        OFFSET
            <int64>$offset
        LIMIT
            <int64>$limit
    """

    files = await conn.query(
        query,
        namespace=str(namespace),
        mediatypes=mediatypes,
        offset=offset,
        limit=limit,
    )
    return [from_db(file) for file in files]


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
    if str(path).lower() != str(next_path).lower():
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
            for sign, parents in zip((-1, 1), (to_decrease, to_increase), strict=True)
        ]
    )

    return file


async def _move_file(conn: DBAnyConn, file_id: StrOrUUID, next_path: StrOrPath) -> File:
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
        await conn.query_required_single(
            query,
            file_id=file_id,
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
    count = await conn.query_required_single("""
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


async def restore_all_folders_size(conn: DBAnyConn, namespace: StrOrPath) -> None:
    """
    Restore size of all folders in a given namespace

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Namespace where a folder size should be restored.
    """
    ns_path = str(namespace)

    home_folder_query = """
        UPDATE File
        FILTER
            .namespace.path = <str>$ns_path
            AND
            .path = '.'
        SET {
            size := (SELECT sum((
                SELECT detached File { size }
                FILTER
                    .namespace.path = <str>$ns_path
                    AND
                    .path LIKE '%'
                    AND
                    .path NOT LIKE '%/%'
            ).size))
        }
    """

    folder_query = """
        WITH
            Parent := File,
        UPDATE File
        FILTER
            .namespace.path = <str>$ns_path
            AND
            .mediatype.name = <str>$mediatype
        SET {
            size := (SELECT sum((
                SELECT Parent { size }
                FILTER
                    Parent.namespace = File.namespace
                    AND
                    Parent.path LIKE File.path ++ '/%'
                    AND
                    Parent.mediatype.name != <str>$mediatype
            ).size))
        }
    """

    await conn.query(folder_query, ns_path=ns_path, mediatype=mediatypes.FOLDER)
    await conn.query(home_folder_query, ns_path=ns_path)
