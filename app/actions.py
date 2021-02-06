from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from app import crud
from app.config import TRASH_FOLDER_NAME
from app.entities import Namespace
from app.storage import storage

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models import File, User


class AlreadyExists(Exception):
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


def _create_home_folder(db_session: Session, namespace: Namespace) -> File:
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


def create_folder(db_session: Session, namespace: Namespace, path: str) -> File:
    """
    Creates a folder in a given Namespace.

    Args:
        db_session (Session): Database session.
        namespace (Namespace): Namespace where a folder should be created.
        path (str): Folder path.

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
