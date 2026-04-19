from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID


class IMediaItemFavouriteRepository(Protocol):
    async def add_batch(
        self, user_id: UUID, media_item_ids: Sequence[UUID]
    ) -> None:
        """Adds multiple favourite media item relations for the user."""

    async def list_ids(self, user_id: UUID) -> list[UUID]:
        """Lists favourite media item IDs for the specified user."""

    async def remove_batch(
        self, user_id: UUID, media_item_ids: Sequence[UUID]
    ) -> None:
        """Removes multiple favourite media item relations for the user."""
