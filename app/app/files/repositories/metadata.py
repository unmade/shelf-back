from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.domain import ContentMetadata


class IContentMetadataRepository(Protocol):
    async def get_by_file_id(self, file_id: UUID) -> ContentMetadata:
        """
        Get metadata associated with a given File ID.

        Args:
            file_id (UUID): Target File ID.

        Raises:
            ContentMetadata.NotFound: If FileMetada for a given file ID does not exist.

        Returns:
            ContentMetadata: File content metadata.
        """

    async def save(self, metadata: ContentMetadata) -> ContentMetadata:
        """
        Save file metadata to the database.

        Args:
            metadata (ContentMetadata): File metadata.

        Raises:
            File.NotFound: If a file with specified ID doesn't exist.

        Returns:
            ContentMetadata: File content metadata.
        """

    async def save_batch(self, metadatas: Iterable[ContentMetadata]) -> None:
        """
        Saves multiple file content metadata at once.

        Args:
            metadatas (Iterable[ContentMetadata]): Iterable of ContentMetadata.
        """
