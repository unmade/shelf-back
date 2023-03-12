from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Protocol

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

    async def save_batch(self, metadatas: Iterable[ContentMetadata]) -> None:
        """
        Saves multiple file content metadata at once.

        Args:
            metadatas (Iterable[ContentMetadata]): Iterable of ContentMetadata.
        """
