from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.photos.domain import Album

__all__ = ["IAlbumRepository"]


class IAlbumRepository(Protocol):
    async def count_by_slug_pattern(self, owner_id: UUID, pattern: str) -> int:
        """Returns the number of occurence of the given slug pattern."""

    async def exists_with_slug(self, owner_id: UUID, slug: str) -> bool:
        """Checks if album with the given slug exists."""

    async def list_by_owner_id(
        self,
        owner_id: UUID,
        *,
        offset: int,
        limit: int = 25,
    ) -> list[Album]:
        """Lists albums of a given owner."""

    async def save(self, entity: Album) -> Album:
        """
        Saves a new album.

        Note, that `cover` field will be ignored even if set on entity.
        """
