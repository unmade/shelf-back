from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from app.app.blobs.domain.blob_job import BlobJob

__all__ = ["IBlobJobRepository"]


class IBlobJobRepository(Protocol):
    async def delete_by_id_batch(self, ids: Sequence[UUID]) -> None:
        """Deletes blob jobs with the given IDs."""

    async def get_by_id_batch(self, ids: Sequence[UUID]) -> list[BlobJob]:
        """Returns blob jobs with the given IDs."""

    async def save_batch(self, jobs: Sequence[BlobJob]) -> list[BlobJob]:
        """Saves multiple blob jobs at once."""
