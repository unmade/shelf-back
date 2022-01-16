from __future__ import annotations

import asyncio
import itertools
import os.path
from collections import deque
from datetime import datetime
from pathlib import PurePath
from typing import IO, TYPE_CHECKING

from app import config, crud, errors, mediatypes
from app.entities import Account, File, Namespace
from app.storage import storage

if TYPE_CHECKING:
    from app.typedefs import DBConnOrPool, DBPool, StrOrPath, StrOrUUID


async def add_bookmark(
    conn: DBConnOrPool,
    user_id: StrOrUUID,
    file_id: StrOrUUID,
) -> None:
    """
    Add a file to user bookmarks.

    Args:
        conn (DBConnOrPool): Database connection.
        user_id (StrOrUUID): Target user ID.
        file_id (StrOrUUID): Target file ID.

    Raises:
        errors.UserNotFound: If User with a target user_id does not exists.
    """
    await crud.user.add_bookmark(conn, user_id, file_id)


async def create_account(
    conn: DBConnOrPool,
    username: str,
    password: str,
    *,
    email: str | None = None,
    first_name: str = "",
    last_name: str = "",
    superuser: bool = False,
) -> Account:
    """
    Create a new user, namespace, home and trash folders.

    Args:
        conn (DBConnOrPool): Database connection or connection pool.
        username (str): Username for a new user.
        password (str): Plain-text password.
        email (str | None, optional): Email. Defaults to None.
        first_name (str, optional): First name. Defaults to "".
        last_name (str, optional): Last name. Defaults to "".
        superuser (bool, optional): Whether user is super user or not. Defaults to
            False.

    Raises:
        UserAlreadyExists: If user with this username or email already exists.

    Returns:
        Account: A freshly created account.
    """
    username = username.lower()
    await storage.makedirs(username, config.TRASH_FOLDER_NAME)

    async for tx in conn.retrying_transaction():  # pragma: no branch
        async with tx:
            user = await crud.user.create(tx, username, password, superuser=superuser)
            namespace = await crud.namespace.create(tx, username, user.id)
            await crud.file.create_home_folder(tx, namespace.path)
            await crud.file.create_folder(tx, namespace.path, config.TRASH_FOLDER_NAME)
            account = await crud.account.create(
                tx, username, email=email, first_name=first_name, last_name=last_name
            )
    return account


async def create_folder(
    conn: DBConnOrPool, namespace: Namespace, path: StrOrPath,
) -> File:
    """
    Create folder with any missing parents in a target Namespace.

    Args:
        conn (DBConnOrPool): Database connection or connection pool.
        namespace (Namespace): Namespace where a folder should be created.
        path (StrOrPath): Path to a folder to create.

    Raises:
        FileAlreadyExists: If folder with this path already exists.
        NotADirectory: If one of the path parents is not a directory.

    Returns:
        File: Created folder.
    """
    await storage.makedirs(namespace.path, path)
    await crud.file.create_folder(conn, namespace.path, path)
    return await crud.file.get(conn, namespace.path, path)


async def delete_immediately(
    conn: DBConnOrPool, namespace: Namespace, path: StrOrPath,
) -> File:
    """
    Permanently delete a file or a folder with all of its contents.

    Args:
        conn (DBConnOrPool): Database connection or connection pool.
        namespace (Namespace): Namespace where file/folder should be deleted.
        path (StrOrPath): Path to a file/folder to delete.

    Raises:
        FileNotFound: If file/folder with a given path does not exists.

    Returns:
        File: Deleted file.
    """
    async for tx in conn.retrying_transaction():  # pragma: no branch
        async with tx:
            file = await crud.file.delete(tx, namespace.path, path)

    await storage.delete(namespace.path, path),
    return file


async def empty_trash(conn: DBConnOrPool, namespace: Namespace) -> File:
    """
    Delete all files and folders in the Trash folder within a target Namespace.

    Args:
        conn (DBConnOrPool): Database connection or connection pool.
        namespace (Namespace): Namespace where Trash folder should be emptied.

    Returns:
        File: Trash folder.
    """
    files = await crud.file.list_folder(conn, namespace.path, config.TRASH_FOLDER_NAME)
    async for tx in conn.retrying_transaction():  # pragma: no branch
        async with tx:
            await crud.file.empty_trash(tx, namespace.path)

    for file in files:
        await storage.delete(namespace.path, file.path)

    return await crud.file.get(conn, namespace.path, config.TRASH_FOLDER_NAME)


async def get_thumbnail(
    conn: DBConnOrPool, namespace: Namespace, path: StrOrPath, *, size: int,
) -> tuple[File, int, IO[bytes]]:
    """
    Generate in-memory thumbnail with preserved aspect ratio.

    Args:
        conn (DBConnOrPool): Database connection or connection pool.
        namespace (Namespace): Namespace where a file is located.
        path (StrOrPath): Path to a file.
        size (int): Thumbnail dimension.

    Raises:
        FileNotFound: If file with this path does not exists.
        IsADirectory: If file is a directory.
        ThumbnailUnavailable: If file is not an image.

    Returns:
        tuple[File, int, BytesIO]: Tuple of file, thumbnail disk size and thumbnail.
    """
    file = await crud.file.get(conn, namespace.path, path)
    thumbsize, thumbnail = await storage.thumbnail(namespace.path, path, size=size)
    return file, thumbsize, thumbnail


async def move(
    conn: DBConnOrPool,
    namespace: Namespace,
    path: StrOrPath,
    next_path: StrOrPath,
) -> File:
    """
    Move a file or folder to a different location in the target Namespace.
    If the source path is a folder all its contents will be moved.

    Args:
        conn (DBConnOrPool): Database connection or connection pool.
        namespace (Namespace): Namespace, where file/folder should be moved.
        path (StrOrPath): Path to be moved.
        next_path (StrOrPath): Path that is the destination.

    Raises:
        errors.FileNotFound: If source path does not exists.
        errors.FileAlreadyExists: If some file already in the destination path.
        errors.MissingParent: If 'next_path' parent does not exists.
        errors.NotADirectory: If one of the 'next_path' parents is not a folder.

    Returns:
        File: Moved file/folder.
    """
    assert str(path).lower() not in (".", config.TRASH_FOLDER_NAME.lower()), (
        "Can't move Home or Trash folder."
    )
    assert not str(next_path).lower().startswith(f"{str(path).lower()}/"), (
        "Can't move to itself."
    )

    if not await crud.file.exists(conn, namespace.path, path):
        raise errors.FileNotFound() from None

    next_parent = os.path.normpath(os.path.dirname(next_path))
    if not await crud.file.exists(conn, namespace.path, next_parent):
        raise errors.MissingParent() from None

    if await crud.file.exists(conn, namespace.path, next_path):
        raise errors.FileAlreadyExists() from None

    await storage.move(namespace.path, path, next_path)

    async for tx in conn.retrying_transaction():  # pragma: no branch
        async with tx:
            file = await crud.file.move(tx, namespace.path, path, next_path)
    return file


async def move_to_trash(
    conn: DBConnOrPool, namespace: Namespace, path: StrOrPath,
) -> File:
    """
    Move a file or folder to the Trash folder in the target Namespace.
    If the path is a folder all its contents will be moved.
    If file with the same name already in the Trash, then path will be renamed.

    Args:
        conn (DBConnOrPool): Database session or connection pool.
        namespace (Namespace): Namespace where path located.
        path (StrOrPath): Path to a file or folder to be moved to the Trash folder.

    Raises:
        errors.FileNotFound: If source path does not exists.

    Returns:
        File: Moved file.
    """
    next_path = PurePath(config.TRASH_FOLDER_NAME) / os.path.basename(path)

    if await crud.file.exists(conn, namespace.path, next_path):
        name = next_path.name.strip(next_path.suffix)
        timestamp = f"{datetime.now():%H%M%S%f}"
        next_path = next_path.parent / f"{name} {timestamp}{next_path.suffix}"

    return await move(conn, namespace, path, next_path)


async def reconcile(conn: DBPool, namespace: Namespace) -> None:
    """
    Create files that are missing in the database, but present in the storage and remove
    files that are present in the database, but missing in the storage.

    Args:
        conn (DBConnOrPool): Database connection or connection pool.
        namespace (Namespace): Namespace where file will be reconciled.

    Raises:
        errors.FileNotFound: If path to a folder does not exists.
        errors.NotADirectory: If path to a folder is not a directory.
    """
    ns_path = str(namespace.path)
    folders = deque(["."])
    missing = []

    # For now, it is faster to re-create all files from scratch
    # than iterating through large directories looking for one missing/dangling file
    await crud.file.reset(conn, ns_path)

    while True:
        try:
            folder = folders.pop()
        except IndexError:
            break

        for file in await storage.iterdir(ns_path, folder):
            if file.is_dir():
                folders.append(file.path)
                size = 0
                mediatype = mediatypes.FOLDER
            else:
                size = file.size
                mediatype = mediatypes.guess(file.name)

            missing.append(
                File(
                    id=None,  # type: ignore
                    name=file.name,
                    path=file.path,
                    size=size,
                    mtime=file.mtime,
                    mediatype=mediatype,
                )
            )

    await asyncio.gather(*(
        crud.file.create_batch(conn, ns_path, files=files)
        for files in itertools.zip_longest(*[iter(missing)] * 500)
    ))


async def remove_bookmark(conn: DBPool, user_id: StrOrUUID, file_id: StrOrUUID) -> None:
    """
    Remove a file from user bookmarks.

    Args:
        conn (DBConnOrPool): Database connection.
        user_id (StrOrUUID): Target user ID.
        file_id (StrOrUUID): Target file ID.

    Raises:
        errors.UserNotFound: If User with a target user_id does not exists.
    """
    await crud.user.remove_bookmark(conn, user_id, file_id)


async def save_file(
    conn: DBPool, namespace: Namespace, path: StrOrPath, content: IO[bytes],
) -> File:
    """
    Save file to storage and database.

    If file name is already taken, then file will be saved under a new name.
    For example - if target name 'f.txt' is taken, then new name will be 'f (1).txt'.

    Args:
        conn (DBConnOrPool): Database connection or connection pool.
        namespace (Namespace): Namespace where a file should be saved.
        path (StrOrPath): Path where a file will be saved.
        content (IO): Actual file.

    Raises:
        NotADirectory: If one of the path parents is not a folder.

    Returns:
        File: Saved file.
    """
    parent = os.path.normpath(os.path.dirname(path))

    if not await crud.file.exists(conn, namespace.path, parent):
        await create_folder(conn, namespace, parent)

    next_path = await crud.file.next_path(conn, namespace.path, path)

    storage_file = await storage.save(namespace.path, next_path, content)

    async for tx in conn.retrying_transaction():  # pragma: no branch
        async with tx:
            file = await crud.file.create(
                tx,
                namespace.path,
                next_path,
                size=storage_file.size,
                mediatype=mediatypes.guess(next_path, content)
            )

    return file
