from __future__ import annotations

from datetime import datetime
from os.path import join as joinpath
from pathlib import Path
from typing import IO, TYPE_CHECKING

from app import crud
from app.config import TRASH_FOLDER_NAME
from app.entities import File, Namespace
from app.storage import storage

if TYPE_CHECKING:
    from edgedb import AsyncIOConnection
    from app.typedefs import StrOrPath


async def create_account(conn: AsyncIOConnection, username: str, password: str) -> None:
    """
    Create new user, namespace, home and trash folders.

    Args:
        db_session (Session): Database session.
        username (str): Username for a new user.
        password (str): Plain-text password.

    Raises:
        UserAlreadyExists: If user with this username already exists.
    """
    async with conn.transaction():
        await crud.user.create(conn, username, password)
        await crud.file.create(conn, username, TRASH_FOLDER_NAME, folder=True)
        storage.mkdir(username)
        storage.mkdir(joinpath(username, TRASH_FOLDER_NAME))


async def create_folder(
    conn: AsyncIOConnection, namespace: Namespace, path: StrOrPath,
) -> File:
    """
    Create folder in a target Namespace.

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
        db_session (Session): Database connection.
        namespace (Namespace): Namespace where file/folder should be deleted.
        path (StrOrPath): Path to a file/folder to delete.

    Raises:
        FileNotFound: If file/folder with a given path does not exists.

    Returns:
        File: Deleted file.
    """
    file = await crud.file.get(conn, namespace.path, path)

    async with conn.transaction():
        await crud.file.delete(conn, namespace.path, path)
        storage.delete(namespace.path / path)

    return file


async def empty_trash(conn: AsyncIOConnection, namespace: Namespace) -> File:
    """
    Delete all files and folders in the Trash folder within a target Namespace.

    Args:
        db_session (AsyncIOConnection): Database connection.
        namespace (Namespace): Namespace where Trash folder should be emptied.

    Returns:
        File: Trash folder.
    """
    async with conn.transaction():
        await crud.file.empty_trash(conn, namespace.path)
        storage.delete_dir_content(namespace.path / TRASH_FOLDER_NAME)
    return await crud.file.get(conn, namespace.path, TRASH_FOLDER_NAME)


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
        await crud.file.move(conn, namespace.path, path, next_path)
        storage.move(namespace.path / path, namespace.path / next_path)
    return await crud.file.get(conn, namespace.path, next_path)


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
    next_path = Path(TRASH_FOLDER_NAME) / Path(path).name

    if await crud.file.exists(conn, namespace.path, next_path):
        name = next_path.name.strip(next_path.suffix)
        timestamp = datetime.now().strftime("%H%M%S%f")
        next_path = next_path.parent / f"{name} {timestamp}{next_path.suffix}"

    return await move(conn, namespace, path, next_path)


async def reconcile(
    conn: AsyncIOConnection, namespace: Namespace, path: StrOrPath,
) -> None:
    """
    Creates files that are missing in the database, but present in the storage.

    Args:
        conn (AsyncIOConnection): Database connection.
        namespace (Namespace): Namespace where file will be reconciled.
        path (StrOrPath): Path to a folder to reconcile.

    Raises:
        errors.FileNotFound: If path to a folder does not exists.
        errors.NotADirectory: If path to a folder is not a directory.
    """
    path = Path(path)

    files_storage = {f.name: f for f in storage.iterdir(namespace.path / path)}
    files_db = await crud.file.list_folder(conn, namespace.path, path, with_trash=True)

    names_storage = set(files_storage.keys())
    names_db = (f.name for f in files_db)

    if names := names_storage.difference(names_db):
        await crud.file.create_batch(
            conn,
            namespace.path,
            path=path,
            files=[
                File.construct(
                    name=file.name,
                    path=file.path.relative_to(namespace.path),
                    size=file.size,
                    mtime=file.mtime,
                    is_dir=file.is_dir,
                )
                for name in names
                if (file := files_storage[name])
            ]
        )

    subdirs = (f for f in files_storage.values() if f.is_dir)
    for subdir in subdirs:
        await reconcile(conn, namespace, subdir.path.relative_to(namespace.path))


async def save_file(
    conn: AsyncIOConnection, namespace: Namespace, path: StrOrPath, file: IO,
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

    if not await crud.file.exists(conn, namespace.path, path.parent, folder=True):
        await create_folder(conn, namespace, path.parent)

    next_path = await crud.file.next_path(conn, namespace.path, path)

    async with conn.transaction():
        await crud.file.create(
            conn,
            namespace.path,
            next_path,
            size=file.seek(0, 2),
        )
        file.seek(0)
        storage.save(namespace.path / next_path, file)

    return await crud.file.get(conn, namespace.path, next_path)
