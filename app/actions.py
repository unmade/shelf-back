from __future__ import annotations

import asyncio
import concurrent.futures
import itertools
from collections import defaultdict, deque
from io import BytesIO
from typing import TYPE_CHECKING

from app import crud, hashes, mediatypes, metadata, taskgroups
from app.entities import File, Fingerprint, Namespace, SharedLink
from app.infrastructure.storage import storage

if TYPE_CHECKING:
    from app.app.infrastructure import IStorage
    from app.entities import Exif
    from app.typedefs import DBClient, StrOrPath, StrOrUUID


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
    storage: IStorage,
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


async def revoke_shared_link(db_client: DBClient, token: str) -> None:
    """
    Revoke shared link token.

    Args:
        db_client (DBClient): Database client.
        token (str): Shared link token to revoke.
    """
    await crud.shared_link.delete(db_client, token)
