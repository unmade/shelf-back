from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from app.app.files.domain import SharedLink
    from app.app.files.services import NamespaceService, SharingService
    from app.app.photos.domain import MediaItem
    from app.app.photos.domain.media_item import (
        MediaItemCategory,
        MediaItemCategoryName,
    )
    from app.app.photos.services import MediaItemService

    class IUseCaseServices(Protocol):
        media_item: MediaItemService
        namespace: NamespaceService
        sharing: SharingService


__all__ = [
    "PhotosUseCase",
]


class PhotosUseCase:
    __slots__ = ["_services", "media_item", "namespace", "sharing"]

    def __init__(self, services: IUseCaseServices):
        self._services = services
        self.media_item = services.media_item
        self.namespace = services.namespace
        self.sharing = services.sharing

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
        self, user_id: UUID, *, only_favourites: bool = False, offset: int, limit: int
    ) -> list[MediaItem]:
        """Lists media items for a given user."""
        return await self.media_item.list_for_user(
            user_id,
            only_favourites=only_favourites,
            offset=offset,
            limit=limit,
        )

    async def list_media_item_categories(
        self, user_id: UUID, file_id: UUID
    ) -> list[MediaItemCategory]:
        """
        Lists categories of the user MediaItem with given ID.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist.
        """
        item = await self.media_item.get_for_user(user_id, file_id)
        return await self.media_item.list_categories(item.file_id)

    async def list_shared_links(
        self, user_id: UUID
    ) -> list[tuple[MediaItem, SharedLink]]:
        """Lists shared links."""
        namespace = await self.namespace.get_by_owner_id(user_id)
        links = await self.sharing.list_links_by_ns(namespace.path, limit=1000)
        file_ids = [link.file_id for link in links]
        items_by_id = {
            item.file_id: item
            for item in await self.media_item.get_by_id_batch(file_ids)
        }
        return [
            (item, link)
            for link in links
            if (item := items_by_id.get(link.file_id))
        ]

    async def set_media_item_categories(
        self, user_id: UUID, file_id: UUID, categories: Sequence[MediaItemCategoryName]
    ) -> None:
        """
        Clears existing and sets specified categories for MediaItem with given file ID.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist.
        """
        item = await self.media_item.get_for_user(user_id, file_id)
        return await self.media_item.set_categories(item.file_id, categories)
