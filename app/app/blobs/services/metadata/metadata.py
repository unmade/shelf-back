from __future__ import annotations

from typing import IO, TYPE_CHECKING, Protocol
from uuid import UUID

from app.app.blobs.domain import BlobMetadata

from . import readers

if TYPE_CHECKING:
    from app.app.blobs.repositories.metadata import IBlobMetadataRepository

    class IServiceDatabase(Protocol):
        blob_metadata: IBlobMetadataRepository


class BlobMetadataService:
    """A service to track and retrieve file content metadata."""

    __slots__ = ["db"]

    def __init__(self, database: IServiceDatabase):
        self.db = database

    async def get_by_blob_id(self, blob_id: UUID) -> BlobMetadata:
        """
        Get metadata associated with a given File ID.

        Raises:
            BlobMetadata.NotFound: If BlobMetadata for a given file ID does not exist.
        """
        return await self.db.blob_metadata.get_by_blob_id(blob_id)

    async def track(self, blob_id: UUID, content: IO[bytes]) -> None:
        """
        Tracks file content metadata.

        Raises:
            Blob.NotFound: If a blob with specified ID doesn't exist.
        """
        data = await readers.load(content)
        if data is None:
            return

        await self.db.blob_metadata.save(
            BlobMetadata(blob_id=blob_id, data=data)
        )
