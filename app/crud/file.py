from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, cast

import edgedb

from app import errors, mediatypes
from app.config import TRASH_FOLDER_NAME
from app.entities import File

if TYPE_CHECKING:
    from uuid import UUID
    from app.typedefs import DBAnyConn, StrOrPath


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
    Create new file.

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
    namespace = Path(namespace)
    path = Path(path)
    mtime = mtime or time.time()

    try:
        parent = await get(conn, namespace, path.parent)
    except errors.FileNotFound as exc:
        raise errors.MissingParent() from exc
    else:
        if not parent.is_folder():
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
                LIMIT 1
            )
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
                parent := parent,
                namespace := parent.namespace,
            }
        ) { id, name, path, size, mtime, mediatype: { name } }
    """

    params = {
        "name": (namespace / path).name,
        "path": str(path),
        "size": size,
        "mtime": time.time(),
        "mediatype": mediatype,
        "namespace": str(namespace),
        "parent": str(path.parent),
    }

    try:
        file = await conn.query_one(query, **params)
    except edgedb.ConstraintViolationError as exc:
        raise errors.FileAlreadyExists() from exc

    if size:
        await inc_size_batch(conn, namespace, path.parents, size)

    return File.from_db(file)


async def create_batch(
    conn: DBAnyConn, namespace: StrOrPath, path: StrOrPath, files: list[File],
) -> None:
    """
    Create files in a given path and updates parents size accordingly.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Namespace where files will be created.
        path (StrOrPath): Path to a folder where files will be created.
        files (list[File]): List of files to create. All files must have 'path'
            as a parent.

    Raises:
        errors.FileAlreadyExists: If some file already exists.
        errors.FileNotFound: If path to a folder does not exists.
        errors.NotADirectory: If path to a folder is not a directory.
    """
    if not files:
        return

    parent = await get(conn, namespace, path)
    if not parent.is_folder():
        raise errors.NotADirectory

    query = """
        WITH
            files := array_unpack(<array<json>>$files),
            parent := (
                SELECT
                    File
                FILTER
                    .path = <str>$parent
                    AND
                    .namespace.path = <str>$namespace
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
                parent := parent,
                namespace := parent.namespace,
            }
        )
    """

    params = {
        "namespace": str(namespace),
        "parent": str(path),
        "files": [file.json() for file in files],
    }

    try:
        await conn.query(query, **params)
    except edgedb.ConstraintViolationError as exc:
        raise errors.FileAlreadyExists() from exc

    if size := sum(f.size for f in files):
        paths = [str(path)] + [str(p) for p in Path(path).parents]
        await inc_size_batch(conn, namespace, paths, size)


async def create_folder(conn: DBAnyConn, namespace: StrOrPath, path: StrOrPath) -> None:
    """
    Create a folder with any missing parents of the target path.

    If target path already exists, do nothing.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Namespace where to create folder to.
        path (StrOrPath): Path in the namespace to create the folder.

    Raises:
        FileAlreadyExists: If folder at target path already exists.
        NotADirectory: If one of the parents is not a directory.
    """
    paths = [str(path)] + [str(p) for p in Path(path).parents]

    parents = await get_many(conn, namespace, paths)
    assert len(parents) > 0, f"No home folder in a namespace: '{namespace}'"

    if any(not p.is_folder() for p in parents):
        raise errors.NotADirectory()
    if str(parents[-1].path) == str(path):
        raise errors.FileAlreadyExists()

    to_create = list(reversed(paths[:paths.index(parents[-1].path)]))

    for p in to_create:
        try:
            await create(conn, namespace, p, mediatype=mediatypes.FOLDER)
        except (errors.FileAlreadyExists, errors.MissingParent):
            pass


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


async def delete_batch(
    conn: DBAnyConn, namespace: StrOrPath, path: StrOrPath, names: Iterable[str],
) -> None:
    """
    Delete all file with target name in specified path and updates parents size.

    Args:
        conn (DBAnyConn): Database connection.
        namespace (StrOrPath): Namespace where to delete files.
        path (StrOrPath): Path where to delete files.
        names (Iterable[str]): File names to delete.
    """
    if not names:
        return

    query = """
        WITH
            Parent := File,
        UPDATE
            Parent
        FILTER
            .namespace.path = <str>$namespace
            AND
            .path IN array_unpack(<array<str>>$parents)
        SET {
            size := .size - sum((
                DELETE
                    File
                FILTER
                    .namespace.path = <str>$namespace
                    AND
                    .name IN array_unpack(<array<str>>$names)
            ).size)
        }
    """

    path = Path(path)
    parents = [str(path)] + [str(p) for p in path.parents]
    names = list(names)
    await conn.query(query, namespace=str(namespace), parents=parents, names=names)


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
            .path LIKE <str>$path ++ '/%'
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
                .path = <str>$path
                AND
                .namespace.path = <str>$namespace
        )
    """

    return cast(
        bool,
        await conn.query_one(query, namespace=str(namespace), path=str(path)),
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
            .path = <str>$path
            AND
            .namespace.path = <str>$namespace
    """
    try:
        return File.from_db(
            await conn.query_one(query, namespace=str(namespace), path=str(path))
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

    return [File.from_db(f) for f in files]


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
    filter_clause = ""
    if not with_trash and str(path) == ".":
        filter_clause = "FILTER .path != 'Trash'"

    query = f"""
        SELECT
            File {{
                mediatype: {{ name }},
                children := (
                    SELECT
                        .<parent[IS File] {{
                            id, name, path, size, mtime, mediatype: {{ name }},
                        }}
                    {filter_clause}
                    ORDER BY
                        (.mediatype.name = '{mediatypes.FOLDER}') DESC
                    THEN
                        .path ASC
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

    if not parent.mediatype.name == mediatypes.FOLDER:
        raise errors.NotADirectory()

    return [File.from_db(child) for child in parent.children]


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
        errors.FileNotFound: If source path does not exists.
        errors.MissingParent: If 'next_path' parent does not exists.
        errors.NotADirectory: If one of the 'next_path' parents is not a folder.

    Returns:
        File: Moved file.
    """
    path = Path(path)
    assert str(path) not in (".", TRASH_FOLDER_NAME), "Can't move Home or Trash folder."
    assert not str(next_path).startswith(f"{path}/"), "Can't move to itself."

    next_path = Path(next_path)

    # this call also ensures path exists
    target = await get(conn, namespace, path)

    try:
        next_parent = await get(conn, namespace, next_path.parent)
    except errors.FileNotFound as exc:
        raise errors.MissingParent() from exc
    else:
        if not next_parent.is_folder():
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
        WITH
            Parent := File,
        SELECT (
            UPDATE
                File
            FILTER
                .id = <uuid>$file_id
            SET {
                name := <str>$name,
                path := <str>$path,
                parent := (
                    SELECT
                        Parent
                    FILTER
                        .path = <str>$next_parent
                        AND
                        .namespace = File.namespace
                    LIMIT 1
                )
            }
        ) { id, name, path, size, mtime, mediatype: { name } }
    """
    return File.from_db(
        await conn.query_one(
            query,
            file_id=str(file_id),
            name=Path(next_path).name,
            path=str(next_path),
            next_parent=str(Path(next_path).parent),
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
            .path LIKE <str>$path ++ '/%'
            AND
            .namespace.path = <str>$namespace
        SET {
            path := re_replace(<str>$path, <str>$next_path, .path)
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
            .path IN array_unpack(<array<str>>$paths)
            AND
            .namespace.path = <str>$namespace
        SET {
            size := .size + <int64>$size
        }
    """, namespace=str(namespace), paths=[str(p) for p in paths], size=size)
