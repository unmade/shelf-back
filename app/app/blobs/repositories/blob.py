from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.blobs.domain import Blob

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

__all__ = ["IBlobRepository"]


class IBlobRepository(Protocol):
    async def delete(self, blob_id: UUID) -> None:
        """Delete a blob by ID."""

    async def delete_batch(self, blob_ids: Sequence[UUID]) -> None:
        """Delete multiple blobs by IDs."""

    async def get_by_id(self, blob_id: UUID) -> Blob:
        """
        Return a blob by ID.

        Raises:
            Blob.NotFound: If blob with a given ID does not exist.
        """

    async def get_by_id_batch(self, blob_ids: Sequence[UUID]) -> list[Blob]:
        """Returns all blobs with target IDs."""

    async def save(self, blob: Blob) -> Blob:
        """
        Save a new blob record.
        """
