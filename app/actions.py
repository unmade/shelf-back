from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from app import crud
from app.config import TRASH_FOLDER_NAME
from app.entities import File, Namespace
from app.storage import storage

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models import User
    from app.models import File as FileModel


class AlreadyExists(Exception):
    pass


class FileNotFound(Exception):
    pass


def create_account(db_session: Session, username: str, password: str) -> User:
    """
    Creates a new user, namespace, home and trash directories.

    Args:
        db_session (Session): Database session.
        username (str): Username for a new user.
        password (str): Plain-text password.

    Returns:
        User: Created User.
    """
    user = crud.user.create(db_session, username, password)
    namespace = crud.namespace.create(db_session, username, owner_id=user.id)
    _create_home_folder(db_session, namespace)
    db_session.flush()
    create_folder(db_session, namespace, path=TRASH_FOLDER_NAME)

    return user


def _create_home_folder(db_session: Session, namespace: Namespace) -> FileModel:
    """
    Creates home folder in a given Namespace.

    Args:
        db_session (Session): Database session.
        namespace (Namespace): Namespace where home folder should be created.

    Returns:
        File: Created home folder.
    """
    home_dir = storage.mkdir(namespace.path)
    return crud.file.create(
        db_session, home_dir, namespace.id, rel_to=namespace.path
    )


def create_folder(db_session: Session, namespace: Namespace, path: str) -> FileModel:
    """
    Creates a folder in a given Namespace.

    Args:
        db_session (Session): Database session.
        namespace (Namespace): Namespace where a folder should be created.
        path (str): Path to a folder to create.

    Raises:
        AlreadyExists: If folder with a given path already exists.

    Returns:
        File: Created folder.
    """
    relpath = Path(path.strip())
    ns_path = Path(namespace.path)
    fullpath = ns_path / relpath

    # todo: should check within database
    if storage.is_dir_exists(fullpath):
        raise AlreadyExists()

    # todo: catch exception if creation fails
    storage.mkdir(fullpath)

    parent = crud.file.get_folder(db_session, namespace.id, str(relpath.parent))
    if not parent:
        parent = crud.file.create_parents(
            db_session,
            [storage.get(ns_path / p) for p in relpath.parents],
            namespace_id=namespace.id,
            rel_to=namespace.path,
        )

    storage_file = storage.get(fullpath)
    folder = crud.file.create(
        db_session,
        storage_file,
        namespace.id,
        rel_to=namespace.path,
        parent_id=parent.id,
    )

    return folder


def delete_immediately(db_session: Session, namespace: Namespace, path: str) -> File:
    """
    Permanently deletes file or a folder with all of its contents.

    Args:
        db_session (Session): Database session.
        namespace (Namespace): Namespace where file/folder should be deleted.
        path (str): Path to a file/folder to delete.

    Raises:
        FileNotFound: If file/folder with a given path does not exists.

    Returns:
        File: Deleted file.
    """
    file_in_db = crud.file.get(db_session, namespace.id, path)
    if not file_in_db:
        raise FileNotFound()

    file = File.from_orm(file_in_db)
    crud.file.inc_folders_size(
        db_session,
        namespace.id,
        paths=(str(p) for p in Path(path).parents),
        size=-file.size,
    )

    crud.file.delete(db_session, namespace.id, path)
    storage.delete(Path(namespace.path) / path)

    return file
