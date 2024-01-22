from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.photos.domain import MediaItem

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from app.app.photos.domain.media_item import MediaItemCategoryName
    from app.app.photos.repositories import IMediaItemRepository

    class IServiceDatabase(Protocol):
        media_item: IMediaItemRepository

__all__ = ["MediaItemService"]


class MediaItemService:
    __slots__ = ["db"]

    def __init__(self, database: IServiceDatabase):
        self.db = database

    async def auto_add_category_batch(
        self, file_id: UUID, categories: Sequence[tuple[MediaItemCategoryName, int]]
    ) -> None:
        """
        Adds a set of AI-recognized categories.

        Raises:
            MediaItem.NotFound: If media item with a given `file_id` does not exist.
        """
        await self.db.media_item.add_category_batch(
            file_id,
            categories=[
                MediaItem.Category(
                    name=name,
                    origin=MediaItem.Category.Origin.AUTO,
                    probability=probability,
                )
                for name, probability in categories
            ]
        )

    async def list_for_user(
        self, user_id: UUID, *, offset: int, limit: int
    ) -> list[MediaItem]:
        """Lists media items for a given user."""
        return await self.db.media_item.list_by_user_id(
            user_id, offset=offset, limit=limit
        )
