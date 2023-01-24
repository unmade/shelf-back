from __future__ import annotations

import asyncio
import concurrent.futures
import itertools
import os.path
from collections import defaultdict, deque
from datetime import datetime
from io import BytesIO
from pathlib import PurePath
from typing import TYPE_CHECKING

from app import config, crud, errors, hashes, mediatypes, metadata, taskgroups
from app.entities import Account, File, Fingerprint, Namespace, SharedLink
from app.storage import storage

if TYPE_CHECKING:
    from app.entities import Exif
    from app.storage.base import Storage
    from app.typedefs import DBClient, StrOrPath, StrOrUUID


async def add_bookmark(
    db_client: DBClient,
    user_id: StrOrUUID,
    file_id: StrOrUUID,
) -> None:
    """
    Add a file to user bookmarks.

    Args:
        db_client (DBClient): Database client.
        user_id (StrOrUUID): Target user ID.
        file_id (StrOrUUID): Target file ID.

    Raises:
        errors.UserNotFound: If User with a target user_id does not exists.
    """
    await crud.user.add_bookmark(db_client, user_id, file_id)


async def create_account(
    db_client: DBClient,
    username: str,
    password: str,
    *,
    email: str | None = None,
    first_name: str = "",
    last_name: str = "",
    superuser: bool = False,
    storage_quota: int | None = None,
) -> Account:
    """
    Create a new user, namespace, home and trash folders.

    Args:
        db_client (DBClient): Database client.
        username (str): Username for a new user.
        password (str): Plain-text password.
        email (str | None, optional): Email. Defaults to None.
        first_name (str, optional): First name. Defaults to "".
        last_name (str, optional): Last name. Defaults to "".
        superuser (bool, optional): Whether user is super user or not. Defaults to
            False.
        storage_quota (int | None, optional): Storage quota for the account. Use None
            for the unlimited quota. Defaults to None.

    Raises:
        UserAlreadyExists: If user with this username or email already exists.

    Returns:
        Account: A freshly created account.
    """
    username = username.lower()
    await storage.makedirs(username, config.TRASH_FOLDER_NAME)

    async for tx in db_client.transaction():  # pragma: no branch
        async with tx:
            user = await crud.user.create(tx, username, password, superuser=superuser)
            namespace = await crud.namespace.create(tx, username, user.id)
            await crud.file.create_home_folder(tx, namespace.path)
            await crud.file.create_folder(tx, namespace.path, config.TRASH_FOLDER_NAME)
            account = await crud.account.create(
                tx,
                username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                storage_quota=storage_quota,
            )
    return account


async def delete_immediately(
    db_client: DBClient, namespace: Namespace, path: StrOrPath,
) -> File:
    """
    Permanently delete a file or a folder with all of its contents.

    Args:
        db_client (DBClient): Database client.
        namespace (Namespace): Namespace where file/folder should be deleted.
        path (StrOrPath): Path to a file/folder to delete.

    Raises:
        FileNotFound: If file/folder with a given path does not exists.

    Returns:
        File: Deleted file.
    """
    file = await crud.file.get(db_client, namespace.path, path)

    delete_from_storage = storage.deletedir if file.is_folder() else storage.delete

    async for tx in db_client.transaction():  # pragma: no branch
        async with tx:
            await crud.file.delete(tx, namespace.path, path)

    await delete_from_storage(namespace.path, path)

    return file


async def empty_trash(db_client: DBClient, namespace: Namespace) -> File:
    """
    Delete all files and folders in the Trash folder within a target Namespace.

    Args:
        db_client (DBClient): Database client.
        namespace (Namespace): Namespace where Trash folder should be emptied.

    Returns:
        File: Trash folder.
    """
    ns_path = namespace.path
    files = await crud.file.list_folder(db_client, ns_path, config.TRASH_FOLDER_NAME)
    async for tx in db_client.transaction():  # pragma: no branch
        async with tx:
            await crud.file.empty_trash(tx, ns_path)

    for file in files:
        if file.is_folder():
            await storage.deletedir(ns_path, file.path)
        else:
            await storage.delete(ns_path, file.path)

    return await crud.file.get(db_client, ns_path, config.TRASH_FOLDER_NAME)


async def find_duplicates(
    db_client: DBClient, namespace: Namespace, path: StrOrPath, max_distance: int = 5,
) -> list[list[Fingerprint]]:
    """
    Find all duplicate fingerprints in a folder, including sub-folders.

    Duplicate fingerprints are grouped into the same list.

    Args:
        db_client (DBClient): Database client.
        namespace (Namespace): Target namespace.
        path (StrOrPath): Folder path where to search for fingerprints.
        max_distance (int, optional): The maximum distance at which two fingerprints
            are considered the same. Defaults to 5.

    Returns:
        list[list[Fingerprint]]: List of lists of duplicate fingerprints.
    """
    def _traverse(graph, node, visited=set()):  # noqa: B006
        """Returns list of all direct/indirect adjacent nodes for a given node."""
        nodes: list[Fingerprint] = []
        if node in visited:
            return nodes
        visited.add(node)
        nodes.append(node)
        for adjacent in graph[node]:
            nodes.extend(_traverse(graph, adjacent))
        return nodes

    # fetch fingerprints and possible duplicates
    ns_path = namespace.path
    intersection = await crud.fingerprint.intersect_in_folder(db_client, ns_path, path)

    # calculate distance and store it as adjacency list
    visited = set()
    matches = defaultdict(list)
    for fp, dupes in intersection.items():
        for dupe in dupes:
            if (fp, dupe) in visited:
                continue
            visited.add((dupe, fp))
            distance = (fp.value ^ dupe.value).bit_count()
            if distance <= max_distance:
                matches[fp].append(dupe)
                matches[dupe].append(fp)

    # traverse adjacency list to group direct/indirect adjacent nodes
    return [
        group
        for node in matches
        if (group := _traverse(matches, node))
    ]


async def get_or_create_shared_link(
    db_client: DBClient, namespace: Namespace, path: StrOrPath,
) -> SharedLink:
    """
    Create a shared link for a file in a given path. If the link already exists than
    existing link will be returned

    Args:
        db_client (DBClient): Database client.
        namespace (Namespace): Namespace where a file is located
        path (StrOrPath): Target file path.

    Raises:
        FileNotFound: If file/folder with a given path does not exists.

    Returns:
        SharedLink: A shared link.
    """
    ns_path = namespace.path
    return await crud.shared_link.get_or_create(db_client, namespace=ns_path, path=path)


async def get_thumbnail(
    db_client: DBClient, namespace: Namespace, file_id: StrOrUUID, *, size: int,
) -> tuple[File, bytes]:
    """
    Generate in-memory thumbnail with preserved aspect ratio.

    Args:
        db_client (DBClient): Database client.
        namespace (Namespace): Namespace where a file is located.
        file_id (StrOrUUID): Target file ID.
        size (int): Thumbnail dimension.

    Raises:
        FileNotFound: If file with this path does not exists.
        IsADirectory: If file is a directory.
        ThumbnailUnavailable: If file is not an image.

    Returns:
        tuple[File, bytes]: Tuple of file and thumbnail content.
    """
    ns_path = namespace.path
    file = await crud.file.get_by_id(db_client, file_id=file_id)
    thumbnail = await storage.thumbnail(ns_path, file.path, size=size)
    return file, thumbnail


async def move(
    db_client: DBClient,
    namespace: Namespace,
    path: StrOrPath,
    next_path: StrOrPath,
) -> File:
    """
    Move a file or folder to a different location in the target Namespace.
    If the source path is a folder all its contents will be moved.

    Args:
        db_client (DBClient): Database client.
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
    path = str(path)
    next_path = str(next_path)

    assert path.lower() not in (".", config.TRASH_FOLDER_NAME.lower()), (
        "Can't move Home or Trash folder."
    )
    assert not next_path.lower().startswith(f"{path.lower()}/"), (
        "Can't move to itself."
    )

    file = await crud.file.get(db_client, namespace.path, path)

    move_in_storage = storage.movedir if file.is_folder() else storage.move

    next_parent = os.path.normpath(os.path.dirname(next_path))
    if not await crud.file.exists(db_client, namespace.path, next_parent):
        raise errors.MissingParent() from None

    if path.lower() != next_path.lower():
        if await crud.file.exists(db_client, namespace.path, next_path):
            raise errors.FileAlreadyExists() from None

    await move_in_storage(namespace.path, path, next_path)

    async for tx in db_client.transaction():  # pragma: no branch
        async with tx:
            file = await crud.file.move(tx, namespace.path, path, next_path)
    return file


async def move_to_trash(
    db_client: DBClient, namespace: Namespace, path: StrOrPath,
) -> File:
    """
    Move a file or folder to the Trash folder in the target Namespace.
    If the path is a folder all its contents will be moved.
    If file with the same name already in the Trash, then path will be renamed.

    Args:
        db_client (DBClient): Database client.
        namespace (Namespace): Namespace where path located.
        path (StrOrPath): Path to a file or folder to be moved to the Trash folder.

    Raises:
        errors.FileNotFound: If source path does not exists.

    Returns:
        File: Moved file.
    """
    next_path = PurePath(config.TRASH_FOLDER_NAME) / os.path.basename(path)

    if await crud.file.exists(db_client, namespace.path, next_path):
        name = next_path.name.strip(next_path.suffix)
        timestamp = f"{datetime.now():%H%M%S%f}"
        next_path = next_path.parent / f"{name} {timestamp}{next_path.suffix}"

    return await move(db_client, namespace, path, next_path)


async def reindex(db_client: DBClient, namespace: Namespace) -> None:
    """
    Create files that are missing in the database, but present in the storage and remove
    files that are present in the database, but missing in the storage.

    Args:
        db_client (DBClient): Database client.
        namespace (Namespace): Namespace where files will be reindexed.
    """
    ns_path = str(namespace.path)
    folders = deque(["."])
    missing = []

    # For now, it is faster to re-create all files from scratch
    # than iterating through large directories looking for one missing/dangling file
    await crud.file.delete_all(db_client, ns_path)
    await crud.file.create_home_folder(db_client, ns_path)

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
                mediatype = mediatypes.guess(file.name, unsafe=True)

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

    mediatype_names = {file.mediatype for file in missing}
    await crud.mediatype.create_missing(db_client, names=mediatype_names)

    chunk_size = min(len(missing), 500)
    await taskgroups.gather(*(
        crud.file.create_batch(db_client, ns_path, files=chunk)
        for chunk in itertools.zip_longest(*[iter(missing)] * chunk_size)
    ))

    await crud.file.restore_all_folders_size(db_client, ns_path)


async def reindex_files_content(db_client: DBClient, namespace: Namespace) -> None:
    """
    Restore additional information about files, such as file fingerprint and content
    metadata.

    Args:
        db_client (DBClient): Database client.
        namespace (Namespace): Namespace where file information will be reindexed.
    """
    loop = asyncio.get_running_loop()

    ns_path = str(namespace.path)
    batch_size = 500
    types = tuple(hashes.SUPPORTED_TYPES | metadata.SUPPORTED_TYPES)
    batches = crud.file.iter_by_mediatypes(
        db_client, ns_path, mediatypes=types, batch_size=batch_size
    )

    async for files in batches:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = await taskgroups.gather(*(
                asyncio.wait_for(
                    loop.run_in_executor(
                        executor,
                        _reindex_content,
                        storage,
                        ns_path,
                        file.path,
                        file.mediatype,
                    ),
                    timeout=None,
                )
                for file in files
            ))

        # delete all fingerprints and metadata first
        file_ids = [file.id for file in files]
        await taskgroups.gather(
            crud.fingerprint.delete_batch(db_client, file_ids=file_ids),
            crud.metadata.delete_batch(db_client, file_ids=file_ids),
        )

        # create it from scratch
        fps = ((path, dhash) for path, dhash, _ in results if dhash is not None)
        data = ((path, meta) for path, _, meta in results if meta is not None)
        await taskgroups.gather(
            crud.fingerprint.create_batch(db_client, ns_path, fingerprints=fps),
            crud.metadata.create_batch(db_client, ns_path, data=data),
        )


def _reindex_content(
    storage: Storage,
    ns_path: StrOrPath,
    path: StrOrPath,
    mediatype: str,
) -> tuple[StrOrPath, int | None, Exif | None]:
    """
    Download file content and calculate a d-hash for a file in a given path.

    The `storage` argument is passed as a workaround to make test work correctly
    when substituting `.location`.
    """
    content = BytesIO()
    chunks = storage.download(ns_path, path)
    for chunk in chunks:
        content.write(chunk)
    dhash = hashes.dhash(content, mediatype=mediatype)
    meta = metadata.load(content, mediatype=mediatype)
    return path, dhash, meta


async def remove_bookmark(
    db_client: DBClient, user_id: StrOrUUID, file_id: StrOrUUID,
) -> None:
    """
    Remove a file from user bookmarks.

    Args:
        db_client (DBClient): Database client.
        user_id (StrOrUUID): Target user ID.
        file_id (StrOrUUID): Target file ID.

    Raises:
        errors.UserNotFound: If User with a target user_id does not exists.
    """
    await crud.user.remove_bookmark(db_client, user_id, file_id)


async def revoke_shared_link(db_client: DBClient, token: str) -> None:
    """
    Revoke shared link token.

    Args:
        db_client (DBClient): Database client.
        token (str): Shared link token to revoke.
    """
    await crud.shared_link.delete(db_client, token)
