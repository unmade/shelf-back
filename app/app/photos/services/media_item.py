from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.photos.domain import MediaItem
from app.toolkit import timezone

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from app.app.photos.domain.media_item import (
        MediaItemCategory,
        MediaItemCategoryName,
    )
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

    async def delete_batch(
        self, user_id: UUID, file_ids: Sequence[UUID]
    ) -> list[MediaItem]:
        """Deletes multiple media items at once."""
        deleted_at = timezone.now()
        return await self.db.media_item.set_deleted_at_batch(
            user_id, file_ids, deleted_at=deleted_at
        )

    async def get_by_id_batch(self, file_ids: Sequence[UUID]) -> list[MediaItem]:
        """Returns all media items with target IDs."""
        return await self.db.media_item.get_by_id_batch(file_ids)

    async def get_for_user(self, user_id: UUID, file_id: UUID) -> MediaItem:
        """
        Gets MediaItem with given file ID for the specified user ID.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist for the specified user.
        """

        return await self.db.media_item.get_by_user_id(user_id, file_id)

    async def list_deleted(self, user_id: UUID) -> list[MediaItem]:
        return await self.db.media_item.list_deleted(user_id)

    async def list_for_user(
        self, user_id: UUID, *, only_favourites: bool = False, offset: int, limit: int
    ) -> list[MediaItem]:
        """Lists media items for a given user."""
        return await self.db.media_item.list_by_user_id(
            user_id, only_favourites=only_favourites, offset=offset, limit=limit
        )

    async def list_categories(self, file_id: UUID) -> list[MediaItemCategory]:
        """
        Lists categories of the MediaItem with specified file ID.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist.
        """
        return await self.db.media_item.list_categories(file_id)

    async def restore_batch(
        self, user_id: UUID, file_ids: Sequence[UUID]
    ) -> list[MediaItem]:
        """Restores multiple media items at once."""
        deleted_at = None
        return await self.db.media_item.set_deleted_at_batch(
            user_id, file_ids, deleted_at=deleted_at
        )

    async def set_categories(
        self, file_id: UUID, categories: Sequence[MediaItemCategoryName]
    ) -> None:
        """
        Clears existing and sets specified categories for MediaItem with given file ID.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist.
        """
        await self.db.media_item.set_categories(
            file_id,
            categories=[
                MediaItem.Category(
                    name=category,
                    origin=MediaItem.Category.Origin.USER,
                    probability=100,
                )
                for category in categories
            ]
        )
