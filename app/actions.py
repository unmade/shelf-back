from __future__ import annotations

from typing import TYPE_CHECKING

from app import crud
from app.entities import File, Namespace, SharedLink
from app.infrastructure.storage import storage

if TYPE_CHECKING:
    from app.typedefs import DBClient, StrOrPath, StrOrUUID


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


async def revoke_shared_link(db_client: DBClient, token: str) -> None:
    """
    Revoke shared link token.

    Args:
        db_client (DBClient): Database client.
        token (str): Shared link token to revoke.
    """
    await crud.shared_link.delete(db_client, token)
