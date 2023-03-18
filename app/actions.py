from __future__ import annotations

from typing import TYPE_CHECKING

from app import crud
from app.entities import File, Namespace
from app.infrastructure.storage import storage

if TYPE_CHECKING:
    from app.typedefs import DBClient, StrOrUUID


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
