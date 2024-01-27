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

    async def get_by_user_id(self, user_id: UUID, file_id: UUID) -> MediaItem:
        """
        Gets MediaItem with given file ID for the specified user ID.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist.
        """

    async def list_by_user_id(
        self,
        user_id: UUID,
        *,
        only_favourites: bool = False,
        offset: int,
        limit: int = 25,
    ) -> list[MediaItem]:
        """Lists all media items for given user."""

    async def list_categories(self, file_id: UUID) -> list[MediaItemCategory]:
        """
        Lists categories of the MediaItem with specified file ID.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist.
        """

    async def set_categories(
        self, file_id: UUID, categories: Sequence[MediaItemCategory]
    ) -> None:
        """
        Clears existing and sets specified categories for MediaItem with given file ID.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist.
        """
