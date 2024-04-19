from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.app.photos.domain import Album

__all__ = ["IAlbumRepository"]


class IAlbumRepository(Protocol):
    async def save(self, entity: Album) -> Album:
        """
        Saves a new album.

        Note, that `cover` field will be ignored even if set on entity.
        """
