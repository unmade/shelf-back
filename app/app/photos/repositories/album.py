from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.photos.domain import Album, MediaItem

__all__ = ["IAlbumRepository"]


class IAlbumRepository(Protocol):
    async def add_items(
        self, owner_id: UUID, slug: str, file_ids: list[UUID]
    ) -> None:
        """Adds items to the album."""

    async def count_by_slug_pattern(self, owner_id: UUID, pattern: str) -> int:
        """Returns the number of occurence of the given slug pattern."""

    async def exists_with_slug(self, owner_id: UUID, slug: str) -> bool:
        """Checks if album with the given slug exists."""

    async def get_by_slug(self, owner_id: UUID, slug: str) -> Album:
        """
        Returns album by its slug.

        Raises:
            Album.NotFound: If Album does not exist.
        """

    async def list_by_owner_id(
        self,
        owner_id: UUID,
        *,
        offset: int,
        limit: int = 25,
    ) -> list[Album]:
        """Lists albums of a given owner."""

    async def list_items(
        self,
        user_id: UUID,
        slug: str,
        *,
        offset: int,
        limit: int = 25,
    ) -> list[MediaItem]:
        """Lists media items in a given album."""

    async def remove_items(
        self, owner_id: UUID, slug: str, file_ids: list[UUID]
    ) -> None:
        """Removes items from the album."""

    async def save(self, entity: Album) -> Album:
        """
        Saves a new album.

        Note, that `cover` field will be ignored even if set on entity.
        """
