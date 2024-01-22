from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from app.app.photos.domain import MediaItem
    from app.app.photos.domain.media_item import MediaItemCategoryName
    from app.app.photos.services import MediaItemService

    class IUseCaseServices(Protocol):
        media_item: MediaItemService

__all__ = [
    "PhotosUseCase",
]


class PhotosUseCase:
    __slots__ = ["_services", "media_item"]

    def __init__(self, services: IUseCaseServices):
        self._services = services
        self.media_item = services.media_item

    async def auto_add_category_batch(
        self, file_id: UUID, categories: Sequence[tuple[MediaItemCategoryName, int]]
    ) -> None:
        """
        Adds a set of categories provided by AI recognition.

        Raises:
            MediaItem.NotFound: If media item with a given `file_id` does not exist.
        """
        await self.media_item.auto_add_category_batch(file_id, categories=categories)

    async def list_media_items(
        self, user_id: UUID, *, offset: int, limit: int
    ) -> list[MediaItem]:
        """Lists media items for a given user."""
        return await self.media_item.list_for_user(user_id, offset=offset, limit=limit)
