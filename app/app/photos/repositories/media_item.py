from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, NamedTuple, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from app.app.photos.domain import MediaItem
    from app.app.photos.domain.media_item import MediaItemCategory


class CountResult(NamedTuple):
    total: int
    deleted: int


class IMediaItemRepository(Protocol):
    async def add_category_batch(
        self, media_item_id: UUID, categories: Sequence[MediaItemCategory]
    ) -> None:
        """Adds multiple categories at once for the specified media item."""

    async def count(self, owner_id: UUID) -> CountResult:
        """Returns total number of media items owner with specified ID has."""

    async def delete_batch(self, ids: Sequence[UUID]) -> None:
        """Permanently deletes media items with specified IDs."""

    async def get_by_id(self, media_item_id: UUID) -> MediaItem:
        """
        Gets MediaItem with given ID.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist.
        """

    async def get_by_id_batch(self, media_item_ids: Sequence[UUID]) -> list[MediaItem]:
        """Gets all media items with target IDs."""

    async def get_for_owner(self, owner_id: UUID, media_item_id: UUID) -> MediaItem:
        """
        Gets MediaItem with given ID for the specified owner.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist.
        """

    async def list_by_owner(
        self,
        owner_id: UUID,
        *,
        only_favourites: bool = False,
        offset: int,
        limit: int = 25,
    ) -> list[MediaItem]:
        """Lists all media items for given owner."""

    async def list_categories(self, media_item_id: UUID) -> list[MediaItemCategory]:
        """
        Lists categories of the MediaItem with specified ID.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist.
        """

    async def list_deleted(
        self, owner_id: UUID, *, offset: int, limit: int = 25
    ) -> list[MediaItem]:
        """Lists deleted media items."""

    async def save(self, item: MediaItem) -> MediaItem:
        """Saves a new media item."""

    async def set_categories(
        self, media_item_id: UUID, categories: Sequence[MediaItemCategory]
    ) -> None:
        """
        Clears existing and sets specified categories for MediaItem with given ID.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist.
        """

    async def set_deleted_at_batch(
        self, owner_id: UUID, ids: Sequence[UUID], deleted_at: datetime | None
    ) -> list[MediaItem]:
        """Set `deleted_at` to the specified value for all provided IDs."""
