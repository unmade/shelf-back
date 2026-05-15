from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypedDict

from app.app.blobs.domain import Blob

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

__all__ = ["IBlobRepository", "BlobUpdate"]


class BlobUpdate(TypedDict, total=False):
    storage_key: str
    size: int
    chash: str
    media_type: str


class IBlobRepository(Protocol):
    async def delete(self, blob_id: UUID) -> None:
        """Delete a blob by ID."""

    async def delete_all_with_prefix(self, prefix: str) -> None:
        """Deletes all blobs with storage keys matching the provided prefix."""

    async def delete_batch(self, blob_ids: Sequence[UUID]) -> None:
        """Delete multiple blobs by IDs."""

    async def exists_with_storage_key(self, storage_key: str) -> bool:
        """Checks whether a blob exists with the provided storage key."""

    async def get_by_id(self, blob_id: UUID) -> Blob:
        """
        Return a blob by ID.

        Raises:
            Blob.NotFound: If blob with a given ID does not exist.
        """

    async def get_by_id_batch(self, blob_ids: Sequence[UUID]) -> list[Blob]:
        """Returns all blobs with target IDs."""

    async def replace_storage_key_prefix(self, at: str, to: str) -> None:
        """Replaces the storage key prefix for all matching blobs."""

    async def save(self, blob: Blob) -> Blob:
        """
        Save a new blob record.
        """

    async def update(self, blob_id: UUID, fields: BlobUpdate) -> None:
        """
        Updates a blob with provided set of fields.

        Raises:
            Blob.NotFound: If blob with a given ID does not exist.
        """
