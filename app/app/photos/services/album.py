from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.infrastructure.database import SENTINEL_ID
from app.app.photos.domain import Album
from app.app.photos.repositories import IAlbumRepository
from app.contrib.slugify import slugify

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from app.app.photos.domain import MediaItem

    class IServiceDatabase(Protocol):
        album: IAlbumRepository


class AlbumService:
    __slots__ = ["db"]

    def __init__(self, database: IServiceDatabase):
        self.db = database

    async def add_items(self, owner_id: UUID, slug: str, file_ids: list[UUID]) -> Album:
        """
        Adds items to the album.

        Raises:
            Album.NotFound: If album does not exist.
        """
        return await self.db.album.add_items(owner_id, slug, file_ids)

    async def create(self, title: str, owner_id: UUID, created_at: datetime) -> Album:
        """Creates a new album."""
        base_slug = slugify(title, allow_unicode=True)
        slug = await self.get_available_slug(owner_id, slug=base_slug)
        return await self.db.album.save(
            Album(
                id=SENTINEL_ID,
                title=title,
                slug=slug,
                owner_id=owner_id,
                created_at=created_at,
            )
        )

    async def delete(self, owner_id: UUID, slug: str) -> Album:
        """
        Deletes the album.

        Raises:
            Album.NotFound: If album does not exist.
        """
        return await self.db.album.delete(owner_id, slug)

    async def get_available_slug(self, owner_id: UUID, slug: str) -> str:
        """
        Returns modified slug if the current one is already taken, otherwise
        returns it unchanged.

        For example, if slug 'my-slug' exists, then method will return `my-slug-1`.
        """
        if not await self.db.album.exists_with_slug(owner_id, slug):
            return slug

        pattern = f"{slug}-[[:digit:]]+$".lower()
        count = await self.db.album.count_by_slug_pattern(owner_id, pattern)
        return f"{slug}-{count + 1}"

    async def get_by_slug(self, owner_id: UUID, slug: str) -> Album:
        """
        Returns album by its slug.

        Raises:
            Album.NotFound: If Album does not exist.
        """
        return await self.db.album.get_by_slug(owner_id, slug)

    async def list_(self, owner_id: UUID, *, offset: int, limit: int) -> list[Album]:
        """Lists albums of the given owner."""
        return await self.db.album.list_by_owner_id(
            owner_id, offset=offset, limit=limit
        )

    async def list_items(
        self,
        owner_id: UUID,
        slug: str,
        *,
        offset: int,
        limit: int,
    ) -> list[MediaItem]:
        """Lists media items in the given album."""
        return await self.db.album.list_items(
            owner_id, slug, offset=offset, limit=limit
        )

    async def remove_cover(self, owner_id: UUID, slug: str) -> Album:
        """
        Removes the album cover.

        Raises:
            Album.NotFound: If album does not exist.
        """
        return await self.db.album.set_cover(owner_id, slug, file_id=None)

    async def remove_items(
        self, owner_id: UUID, slug: str, file_ids: list[UUID]
    ) -> Album:
        """
        Removes items from the album.

        Raises:
            Album.NotFound: If album does not exist.
        """
        return await self.db.album.remove_items(owner_id, slug, file_ids)

    async def rename(
        self, owner_id: UUID, slug: str, new_title: str
    ) -> Album:
        """
        Renames the album.

        Raises:
            Album.NotFound: If album does not exist.
        """
        album = await self.db.album.get_by_slug(owner_id, slug)
        if album.title == new_title:
            return album

        new_slug = await self.get_available_slug(owner_id, slug=slugify(new_title))
        return await self.db.album.update(album, title=new_title, slug=new_slug)

    async def set_cover(self, owner_id: UUID, slug: str, file_id: UUID | None) -> Album:
        """
        Sets the album cover.

        Raises:
            Album.NotFound: If album does not exist.
        """
        return await self.db.album.set_cover(owner_id, slug, file_id)
