from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.blobs.domain import BlobMetadata

if TYPE_CHECKING:
    from uuid import UUID

__all__ = ["IBlobMetadataRepository"]


class IBlobMetadataRepository(Protocol):
    async def get_by_blob_id(self, blob_id: UUID) -> BlobMetadata:
        """
        Get metadata by blob ID.

        Raises:
            BlobMetadata.NotFound: If metadata for the given blob ID does not exist.
        """

    async def save(self, metadata: BlobMetadata) -> BlobMetadata:
        """Save blob metadata."""
