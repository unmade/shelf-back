from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.photos.domain import MediaItem


class IMediaItemRepository(Protocol):
    async def list_by_user_id(
        self,
        user_id: UUID,
        *,
        offset: int,
        limit: int = 25,
    ) -> list[MediaItem]:
        """Lists all media items for given user."""
