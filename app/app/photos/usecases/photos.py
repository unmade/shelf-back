from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.photos.domain import MediaItem
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

    async def list_media_items(
        self, user_id: UUID, *, offset: int, limit: int
    ) -> list[MediaItem]:
        """Lists media items for a given user."""
        return await self.media_item.list_for_user(user_id, offset=offset, limit=limit)
