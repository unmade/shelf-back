from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.photos.domain import MediaItem
    from app.app.photos.repositories import IMediaItemRepository

    class IServiceDatabase(Protocol):
        media_item: IMediaItemRepository

__all__ = ["MediaItemService"]


class MediaItemService:
    __slots__ = ["db"]

    def __init__(self, database: IServiceDatabase):
        self.db = database

    async def list_for_user(
        self, user_id: UUID, *, offset: int, limit: int
    ) -> list[MediaItem]:
        """Lists media items for a given user."""
        return await self.db.media_item.list_by_user_id(
            user_id, offset=offset, limit=limit
        )
