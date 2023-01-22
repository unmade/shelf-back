from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.domain.entities import ContentMetadata


class IContentMetadataRepository(Protocol):
    async def save(self, metadata: ContentMetadata) -> None:
        """
        Save file metadata to the database.

        Args:
            metadata (ContentMetadata): File metadata.

        Raises:
            errors.FileNotFound: If a file with specified ID doesn't exist.
        """
