from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from app.app.photos.domain import MediaItem
    from app.app.photos.domain.media_item import MediaItemCategory


class IMediaItemRepository(Protocol):
    async def add_category_batch(
        self, file_id: UUID, categories: Sequence[MediaItemCategory]
    ) -> None:
        """Adds multiple categories at once for the specified media item."""

    async def list_by_user_id(
        self,
        user_id: UUID,
        *,
        offset: int,
        limit: int = 25,
    ) -> list[MediaItem]:
        """Lists all media items for given user."""
