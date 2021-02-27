from __future__ import annotations

import asyncio
import functools
import itertools
from datetime import datetime
from os.path import join as joinpath
from pathlib import Path
from typing import IO, TYPE_CHECKING

from app import config, crud, mediatypes
from app.entities import File, Namespace
from app.storage import storage

if TYPE_CHECKING:
    from edgedb import AsyncIOConnection
    from app.typedefs import StrOrPath


async def create_account(conn: AsyncIOConnection, username: str, password: str) -> None:
    """
    Create new user, namespace, home and trash folders.

    Args:
        conn (AsyncIOConnection): Database session.
        username (str): Username for a new user.
        password (str): Plain-text password.

    Raises:
        UserAlreadyExists: If user with this username already exists.
    """
    async with conn.transaction():
        await crud.user.create(conn, username, password)
        await crud.file.create(
            conn, username, config.TRASH_FOLDER_NAME, mediatype=mediatypes.FOLDER
        )
        storage.mkdir(username)
        storage.mkdir(joinpath(username, config.TRASH_FOLDER_NAME))


async def create_folder(
    conn: AsyncIOConnection, namespace: Namespace, path: StrOrPath,
) -> File:
    """
    Create folder with any missing parents in a target Namespace.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (Namespace): Namespace where a folder should be created.
        path (StrOrPath): Path to a folder to create.

    Raises:
        FileAlreadyExists: If folder with this path already exists.
        NotADirectory: If one of the path parents is not a directory.

    Returns:
        File: Created folder.
    """
    storage.mkdir(namespace.path / path)
    await crud.file.create_folder(conn, namespace.path, path)
    return await crud.file.get(conn, namespace.path, path)


async def delete_immediately(
    conn: AsyncIOConnection, namespace: Namespace, path: StrOrPath,
) -> File:
    """
    Permanently delete file or a folder with all of its contents.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (Namespace): Namespace where file/folder should be deleted.
        path (StrOrPath): Path to a file/folder to delete.

    Raises:
        FileNotFound: If file/folder with a given path does not exists.

    Returns:
        File: Deleted file.
    """
    async with conn.transaction():
        file = await crud.file.delete(conn, namespace.path, path)
        storage.delete(namespace.path / path)
    return file


async def empty_trash(conn: AsyncIOConnection, namespace: Namespace) -> File:
    """
    Delete all files and folders in the Trash folder within a target Namespace.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (Namespace): Namespace where Trash folder should be emptied.

    Returns:
        File: Trash folder.
    """
    async with conn.transaction():
        trash = await crud.file.empty_trash(conn, namespace.path)
        storage.delete_dir_content(namespace.path / config.TRASH_FOLDER_NAME)
    return trash


async def get_thumbnail(
    conn: AsyncIOConnection, namespace: Namespace, path: StrOrPath, *, size: int,
) -> tuple[File, int, IO[bytes]]:
    """
    Generate in-memory thumbnail with preserved aspect ratio.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (Namespace): Namespace where a file is located.
        path (StrOrPath): Path to a file.
        size (int): Thumbnail dimension.

    Raises:
        FileNotFound: If file with this path does not exists.
        IsADirectory: If file is a directory.
        ThumbnailUnavailable: If file is not an image.

    Returns:
        tuple[File, int, IO[bytes]]: Tuple of file, thumbnail disk size and thumbnail.
    """
    file = await crud.file.get(conn, namespace.path, path)
    loop = asyncio.get_running_loop()
    func = functools.partial(storage.thumbnail, path=namespace.path / path, size=size)
    thumbsize, thumbnail = await loop.run_in_executor(None, func)

    return file, thumbsize, thumbnail


async def move(
    conn: AsyncIOConnection,
    namespace: Namespace,
    path: StrOrPath,
    next_path: StrOrPath,
) -> File:
    """
    Move a file or folder to a different location in the target Namespace.
    If the source path is a folder all its contents will be moved.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (Namespace): Namespace, where file/folder should be moved.
        path (StrOrPath): Path to be moved.
        next_path (StrOrPath): Path that is the destination.

    Raises:
        errors.FileNotFound: If source path does not exists.
        errors.FileAlreadyExists: If some file already in the destionation path.
        errors.MissingParent: If 'next_path' parent does not exists.
        errors.NotADirectory: If one of the 'next_path' parents is not a folder.

    Returns:
        File: Moved file/folder.
    """
    async with conn.transaction():
        file = await crud.file.move(conn, namespace.path, path, next_path)
        storage.move(namespace.path / path, namespace.path / next_path)
    return file


async def move_to_trash(
    conn: AsyncIOConnection,
    namespace: Namespace,
    path: StrOrPath
) -> File:
    """
    Move a file or folder to the Trash folder in the target Namespace.
    If the path is a folder all its contents will be moved.
    If file with the same name already in the Trash, then path will be renamed.

    Args:
        conn (AsyncIOConnection): Database session.
        namespace (Namespace): Namespace where path located.
        path (StrOrPath): Path to a file or folder to be moved to the Trash folder.

    Raises:
        errors.FileNotFound: If source path does not exists.

    Returns:
        File: Moved file.
    """
    next_path = Path(config.TRASH_FOLDER_NAME) / Path(path).name

    if await crud.file.exists(conn, namespace.path, next_path):
        name = next_path.name.strip(next_path.suffix)
        timestamp = f"{datetime.now():%H%M%S%f}"
        next_path = next_path.parent / f"{name} {timestamp}{next_path.suffix}"

    return await move(conn, namespace, path, next_path)


async def reconcile(
    conn: AsyncIOConnection, namespace: Namespace, path: StrOrPath,
) -> None:
    """
    Create files that are missing in the database, but present in the storage and remove
    files that are present in the database, but missing in the storage.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (Namespace): Namespace where file will be reconciled.
        path (StrOrPath): Path to a folder to reconcile.

    Raises:
        errors.FileNotFound: If path to a folder does not exists.
        errors.NotADirectory: If path to a folder is not a directory.
    """
    for root, dirs, files in storage.walk(namespace.path / path):
        root = root.relative_to(namespace.path)
        in_storage = {f.name: f for f in itertools.chain(dirs, files)}
        in_db = await crud.file.list_folder(conn, namespace.path, root, with_trash=True)

        names_storage = set(in_storage.keys())
        names_db = set(f.name for f in in_db)

        missing = [
            File.construct(  # type: ignore
                name=file.name,
                path=str(file.path.relative_to(namespace.path)),
                size=0 if file.is_dir else file.size,
                mtime=file.mtime,
                mediatype=(
                    mediatypes.FOLDER if file.is_dir else mediatypes.guess(file.name)
                ),
            )
            for name in names_storage.difference(names_db)
            if (file := in_storage[name])
        ]
        await crud.file.create_batch(conn, namespace.path, root, files=missing)

        stale = names_db.difference(names_storage)
        await crud.file.delete_batch(conn, namespace.path, root, names=stale)


async def save_file(
    conn: AsyncIOConnection, namespace: Namespace, path: StrOrPath, file: IO[bytes],
) -> File:
    """
    Save file to storage and database.

    If file name is already taken, then file will be saved under a new name.
    For example - if target name 'f.txt' is taken, then new name will be 'f (1).txt'.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (Namespace): Namespace where a file should be saved.
        path (StrOrPath): Path where a file will be saved.
        file (IO): Actual file.

    Raises:
        NotADirectory: If one of the path parents is not a folder.

    Returns:
        File: Saved file.
    """
    path = Path(path)

    if not await crud.file.exists(conn, namespace.path, path.parent):
        await create_folder(conn, namespace, path.parent)

    next_path = await crud.file.next_path(conn, namespace.path, path)

    size = file.seek(0, 2)
    file.seek(0)

    async with conn.transaction():
        file_db = await crud.file.create(
            conn,
            namespace.path,
            next_path,
            size=size,
            mediatype=mediatypes.guess(next_path, file)
        )
        storage.save(namespace.path / next_path, file)

    return file_db
