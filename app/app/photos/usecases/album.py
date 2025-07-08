from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.photos.domain import Album
from app.toolkit import timezone

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.photos.domain import MediaItem
    from app.app.photos.services import AlbumService

    class IUseCaseServices(Protocol):
        album: AlbumService

__all__ = [
    "AlbumUseCase",
]


class AlbumUseCase:
    __slots__ = ["_services", "album"]

    def __init__(self, services: IUseCaseServices):
        self._services = services
        self.album = services.album

    async def add_album_items(
        self, owner_id: UUID, slug: str, file_ids: list[UUID]
    ) -> None:
        """Adds items to the album."""
        await self.album.add_items(owner_id, slug, file_ids)

    async def create(self, title: str, owner_id: UUID) -> Album:
        """Creates a new album."""
        return await self.album.create(
            title=title,
            owner_id=owner_id,
            created_at=timezone.now(),
        )

    async def get_by_slug(self, owner_id: UUID, slug: str) -> Album:
        """Returns album by its slug."""
        return await self.album.get_by_slug(owner_id, slug)

    async def list_(
        self,
        owner_id: UUID,
        *,
        offset: int,
        limit: int = 25,
    ) -> list[Album]:
        """Lists albums of the given owner."""
        return await self.album.list_(owner_id, offset=offset, limit=limit)

    async def list_items(
        self,
        owner_id: UUID,
        slug: str,
        *,
        offset: int,
        limit: int = 25,
    ) -> list[MediaItem]:
        """Lists media items in the given album."""
        return await self.album.list_items(owner_id, slug, offset=offset, limit=limit)

    async def remove_album_items(
        self, owner_id: UUID, slug: str, file_ids: list[UUID]
    ) -> None:
        """Removes items from the album."""
        await self.album.remove_items(owner_id, slug, file_ids)
