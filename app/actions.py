from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import IO, TYPE_CHECKING

from app import crud
from app.config import TRASH_FOLDER_NAME
from app.entities import File, Namespace
from app.storage import storage

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.models import User
    from app.models import File as FileModel


class FileAlreadyExists(Exception):
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
        FileAlreadyExists: If folder with a given path already exists.

    Returns:
        File: Created folder.
    """
    relpath = Path(path.strip())
    ns_path = Path(namespace.path)
    fullpath = ns_path / relpath

    # todo: should check within database
    if storage.is_dir_exists(fullpath):
        raise FileAlreadyExists()

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
    storage.delete_dir_content(Path(namespace.path) / TRASH_FOLDER_NAME)
    return File.from_orm(
        crud.file.get(db_session, namespace.id, TRASH_FOLDER_NAME)
    )


def move(
    db_session: Session, namespace: Namespace, from_path: str, to_path: str,
) -> File:
    """
    Moves a file or folder to a different location in the given Namespace.
    If the source path is a folder all its contents will be moved.

    Args:
        db_session (Session): Database session.
        namespace (Namespace): Namespace, where file/folder should be moved.
        from_path (str): Path to be moved.
        to_path (str): Path that is the destination.

    Raises:
        FileNotFound: If source path does not exists.
        FileAlreadyExists: If some file already in the destionation path.

    Returns:
        File: Moved file/folder.
    """
    from_path = Path(from_path)
    to_path = Path(to_path)
    ns_path = Path(namespace.path)

    file = crud.file.get(db_session, namespace.id, str(from_path))
    if not file:
        raise FileNotFound()

    if crud.file.get(db_session, namespace.id, str(to_path)):
        raise FileAlreadyExists()

    next_parent = crud.file.get(db_session, namespace.id, str(to_path.parent))
    if not next_parent:
        storage.mkdir(ns_path / to_path.parent)
        next_parent = crud.file.create_parents(
            db_session,
            [storage.get(ns_path / p) for p in to_path.parents],
            namespace_id=namespace.id,
            rel_to=namespace.path,
        )

    file.parent_id = next_parent.id
    file.name = to_path.name
    crud.file.move(db_session, namespace.id, str(from_path), str(to_path))

    folders_to_decrease = set(from_path.parents).difference(to_path.parents)
    if folders_to_decrease:
        crud.file.inc_folders_size(
            db_session,
            namespace.id,
            paths=(str(p) for p in folders_to_decrease),
            size=-file.size,
        )

    folders_to_increase = set(to_path.parents).difference(from_path.parents)
    if folders_to_increase:
        crud.file.inc_folders_size(
            db_session,
            namespace.id,
            paths=(str(p) for p in folders_to_increase),
            size=file.size,
        )

    storage.move(ns_path / from_path, ns_path / to_path)

    db_session.refresh(file)

    return File.from_orm(file)


def move_to_trash(db_session: Session, namespace: Namespace, path: str) -> File:
    """
    Moves a file or folder to the Trash folder in the given Namespace.
    If the path is a folder all its contents will be moved.

    Args:
        db_session (Session): Database session.
        namespace (Namespace): Namespace where path located.
        path (str): Path to a file or folder to be moved to the Trash folder.

    Raises:
        FileNotFound: If source path does not exists.

    Returns:
        File: Moved file.
    """
    from_path = Path(path)
    to_path = Path(TRASH_FOLDER_NAME) / from_path.name
    file = crud.file.get(db_session, namespace.id, str(from_path))
    if not file:
        raise FileNotFound()

    if crud.file.get(db_session, namespace.id, str(to_path)):
        name = to_path.name.strip(to_path.suffix)
        suffix = datetime.now().strftime("%H%M%S%f")
        to_path = to_path.parent / f"{name} {suffix}{to_path.suffix}"

    return move(db_session, namespace, path, str(to_path))


def reconcile(db_session: Session, namespace: Namespace, path: str) -> None:
    """
    Reconciles storage and database in a given folder.

    Args:
        db_session (Session): Database session.
        namespace (Namespace): Namespace where file should be reconciled.
        path (str): Path to a folder that should be reconciled. For home directory
        use ".".
    """
    path = Path(namespace.path) / path
    files = {f.name: f for f in storage.iterdir(path)}

    rel_path = str(path.relative_to(namespace.path))
    parent = crud.file.get_folder(db_session, namespace.id, path=rel_path)
    assert parent is not None
    files_db = crud.file.list_folder_by_id(
        db_session, parent.id, hide_trash_folder=False
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
            path=rel_path,
            size=sum(files[name].size for name in names),
        )

    subdirs = (f for f in storage.iterdir(path) if f.is_dir())
    for subdir in subdirs:
        reconcile(db_session, namespace, subdir.path.relative_to(namespace.path))


def save_file(db_session: Session, namespace: Namespace, path: str, file: IO) -> File:
    """
    Saves file to storage and database.

    Args:
        db_session (Session): Database session.
        namespace (Namespace): Namespace where a file should be saved.
        path (str): Path where a file should be saved.
        file (IO): Actual file.

    Returns:
        File: Saved file.
    """
    relpath = Path(path)
    ns_path = Path(namespace.path)
    fullpath = ns_path / relpath

    if not storage.is_dir_exists(fullpath.parent):
        # todo: catch exception if creation fails
        storage.mkdir(fullpath.parent)

    parent = crud.file.get_folder(db_session, namespace.id, str(relpath.parent))
    if not parent:
        parent = crud.file.create_parents(
            db_session,
            [storage.get(ns_path / p) for p in relpath.parents],
            namespace_id=namespace.id,
            rel_to=namespace.path,
        )

    file_exists = storage.is_exists(fullpath)
    storage_file = storage.save(fullpath, file)

    if file_exists:
        prev_file = storage.get(fullpath)
        result = crud.file.update(
            db_session,
            storage_file,
            namespace_id=namespace.id,
            rel_to=namespace.path,
        )
        size_inc = storage_file.size - prev_file.size
    else:
        result = crud.file.create(
            db_session,
            storage_file,
            namespace_id=namespace.id,
            rel_to=namespace.path,
            parent_id=parent.id,
        )
        size_inc = storage_file.size

    crud.file.inc_folder_size(
        db_session, namespace_id=namespace.id, path=result.path, size=size_inc,
    )

    db_session.flush()
    db_session.refresh(result)

    return File.from_orm(result)
