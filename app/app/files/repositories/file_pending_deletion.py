from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from app.app.files.domain import FilePendingDeletion

__all__ = [
    "IFilePendingDeletionRepository",
]


class IFilePendingDeletionRepository(Protocol):
    async def delete_by_id_batch(
        self, ids: Sequence[UUID]
    ) -> list[FilePendingDeletion]:
        """Deletes multiple pending deletions."""

    async def get_by_id_batch(self, ids: Sequence[UUID]) -> list[FilePendingDeletion]:
        """Returns pending deletion with provided IDs."""

    async def save_batch(
        self, entities: Sequence[FilePendingDeletion]
    ) -> list[FilePendingDeletion]:
        """Saves multiple FilePendingDeletion at once."""
