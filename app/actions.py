from __future__ import annotations

from datetime import datetime
from os.path import join as joinpath
from pathlib import Path
from typing import IO, TYPE_CHECKING

import app.storage
from app import crud
from app.config import TRASH_FOLDER_NAME
from app.crud.user import UserAlreadyExists
from app.entities import File, Namespace
from app.storage import storage

if TYPE_CHECKING:
    from edgedb import AsyncIOConnection
    from sqlalchemy.orm import Session
    from app.typedefs import StrOrPath


class FileAlreadyExists(Exception):
    pass


class FileNotFound(Exception):
    pass


class NotADirectory(Exception):
    pass


class UserAlreadyExist(Exception):
    pass


async def create_account(conn: AsyncIOConnection, username: str, password: str) -> None:
    """
    Create new user, namespace, home and trash folders.

    Args:
        db_session (Session): Database session.
        username (str): Username for a new user.
        password (str): Plain-text password.
    """
    async with conn.transaction():
        try:
            await crud.user.create(conn, username, password)
        except crud.user.UserAlreadyExists as exc:
            raise UserAlreadyExists() from exc
        else:
            await crud.file.create(conn, username, TRASH_FOLDER_NAME, folder=True)
            storage.mkdir(username)
            storage.mkdir(joinpath(username, TRASH_FOLDER_NAME))


async def create_folder(
    conn: AsyncIOConnection, namespace: StrOrPath, path: StrOrPath,
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

    try:
        storage.mkdir(joinpath(namespace, path))
    except app.storage.NotADirectory as exc:
        raise NotADirectory() from exc

    try:
        await crud.file.create_folder(conn, namespace, path)
    except crud.file.FileAlreadyExists as exc:
        raise FileAlreadyExists() from exc

    return await crud.file.get(conn, namespace, path)


def delete_immediately(
    db_session: Session, namespace: Namespace, path: StrOrPath,
) -> File:
    """
    Permanently deletes file or a folder with all of its contents.

    Args:
        db_session (Session): Database session.
        namespace (Namespace): Namespace where file/folder should be deleted.
        path (StrOrPath): Path to a file/folder to delete.

    Raises:
        FileNotFound: If file/folder with a given path does not exists.

    Returns:
        File: Deleted file.
    """
    file_in_db = crud.file.get(db_session, namespace.id, path)
    if not file_in_db:
        raise FileNotFound()

    file = File.from_orm(file_in_db)
    crud.file.inc_folder_size(
        db_session,
        namespace.id,
        path=Path(path).parent,
        size=-file.size,
    )

    crud.file.delete(db_session, namespace.id, path)
    storage.delete(namespace.path / path)

    return file


def empty_trash(db_session: Session, namespace: Namespace) -> File:
    """
    Deletes all files and folders in the Trash folder in a given Namespace.

    Args:
        db_session (Session): Database session.
        namespace (Namespace): Namespace where Trash folder should be emptied.

    Returns:
        File: Trash folder.
    """
    crud.file.empty_trash(db_session, namespace.id)
    storage.delete_dir_content(namespace.path / TRASH_FOLDER_NAME)
    return File.from_orm(
        crud.file.get(db_session, namespace.id, TRASH_FOLDER_NAME)
    )


def move(
    db_session: Session, namespace: Namespace, from_path: StrOrPath, to_path: StrOrPath,
) -> File:
    """
    Moves a file or folder to a different location in the given Namespace.
    If the source path is a folder all its contents will be moved.

    Args:
        db_session (Session): Database session.
        namespace (Namespace): Namespace, where file/folder should be moved.
        from_path (StrOrPath): Path to be moved.
        to_path (StrOrPath): Path that is the destination.

    Raises:
        FileNotFound: If source path does not exists.
        FileAlreadyExists: If some file already in the destionation path.

    Returns:
        File: Moved file/folder.
    """
    from_path = Path(from_path)
    to_path = Path(to_path)

    file = crud.file.get(db_session, namespace.id, from_path)
    if not file:
        raise FileNotFound()

    if crud.file.exists(db_session, namespace.id, to_path):
        raise FileAlreadyExists()

    next_parent = crud.file.get(db_session, namespace.id, to_path.parent)
    if not next_parent:
        next_parent = create_folder(db_session, namespace, to_path.parent)

    file.parent_id = next_parent.id
    file.name = to_path.name
    crud.file.move(db_session, namespace.id, from_path, to_path)

    folders_to_decrease = set(from_path.parents).difference(to_path.parents)
    if folders_to_decrease:
        crud.file.inc_folder_size(
            db_session,
            namespace.id,
            path=max((str(p) for p in folders_to_decrease), key=len),
            size=-file.size,
        )

    folders_to_increase = set(to_path.parents).difference(from_path.parents)
    if folders_to_increase:
        crud.file.inc_folder_size(
            db_session,
            namespace.id,
            path=max((str(p) for p in folders_to_increase), key=len),
            size=file.size,
        )

    storage.move(namespace.path / from_path, namespace.path / to_path)

    db_session.flush()
    db_session.refresh(file)

    return File.from_orm(file)


def move_to_trash(db_session: Session, namespace: Namespace, path: StrOrPath) -> File:
    """
    Moves a file or folder to the Trash folder in the given Namespace.
    If the path is a folder all its contents will be moved.

    Args:
        db_session (Session): Database session.
        namespace (Namespace): Namespace where path located.
        path (StrOrPath): Path to a file or folder to be moved to the Trash folder.

    Raises:
        FileNotFound: If source path does not exists.

    Returns:
        File: Moved file.
    """
    from_path = Path(path)
    to_path = Path(TRASH_FOLDER_NAME) / from_path.name
    file = crud.file.get(db_session, namespace.id, from_path)
    if not file:
        raise FileNotFound()

    if crud.file.exists(db_session, namespace.id, to_path):
        name = to_path.name.strip(to_path.suffix)
        suffix = datetime.now().strftime("%H%M%S%f")
        to_path = to_path.parent / f"{name} {suffix}{to_path.suffix}"

    return move(db_session, namespace, path, to_path)


def reconcile(db_session: Session, namespace: Namespace, path: StrOrPath) -> None:
    """
    Reconciles storage and database in a given folder.

    Args:
        db_session (Session): Database session.
        namespace (Namespace): Namespace where file should be reconciled.
        path (StrOrPath): Path to a folder that should be reconciled. For home
            directory use ".".
    """
    fullpath = namespace.path / path
    files = {f.name: f for f in storage.iterdir(fullpath)}

    relpath = fullpath.relative_to(namespace.path)
    parent = crud.file.get_folder(db_session, namespace.id, path=relpath)
    assert parent is not None
    files_db = crud.file.list_folder_by_id(
        db_session, parent.id, hide_trash_folder=False,
    )

    names_from_storage = set(files.keys())
    names_from_db = (f.name for f in files_db)

    if names := names_from_storage.difference(names_from_db):
        crud.file.bulk_create(
            db_session,
            (files[name] for name in names),
            namespace_id=namespace.id,
            parent_id=parent.id,
            rel_to=namespace.path,
        )
        crud.file.inc_folder_size(
            db_session,
            namespace.id,
            path=relpath,
            size=sum(files[name].size for name in names),
        )

    subdirs = (f for f in storage.iterdir(fullpath) if f.is_dir())
    for subdir in subdirs:
        reconcile(db_session, namespace, subdir.path.relative_to(namespace.path))


def save_file(
    db_session: Session, namespace: Namespace, path: StrOrPath, file: IO,
) -> File:
    """
    Saves file to storage and database.

    Args:
        db_session (Session): Database session.
        namespace (Namespace): Namespace where a file should be saved.
        path (StrOrPath): Path where a file should be saved.
        file (IO): Actual file.

    Returns:
        File: Saved file.
    """
    relpath = Path(path)
    fullpath = namespace.path / relpath

    parent = crud.file.get_folder(db_session, namespace.id, relpath.parent)
    if not parent:
        parent = create_folder(db_session, namespace, relpath.parent)

    storage_file = storage.save(fullpath, file)
    if prev_file := crud.file.get(db_session, namespace.id, fullpath):
        result = crud.file.update(
            db_session,
            storage_file,
            namespace_id=namespace.id,
            rel_to=namespace.path,
        )
    else:
        result = crud.file.create(
            db_session,
            storage_file,
            namespace_id=namespace.id,
            rel_to=namespace.path,
            parent_id=parent.id,
        )

    if prev_file is not None:
        size_inc = storage_file.size - prev_file.size
    else:
        size_inc = storage_file.size

    crud.file.inc_folder_size(db_session, namespace.id, result.path, size=size_inc)

    db_session.refresh(result)

    return File.from_orm(result)
