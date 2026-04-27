from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.infrastructure.database import IAtomic
from app.app.photos.domain import MediaItem

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable, Sequence
    from uuid import UUID

    from app.app.blobs.domain import BlobMetadata, IBlobContent
    from app.app.blobs.services import (
        BlobContentProcessor,
        BlobMetadataService,
        BlobThumbnailService,
    )
    from app.app.photos.domain.media_item import (
        MediaItemCategory,
        MediaItemCategoryName,
    )
    from app.app.photos.repositories.media_item import CountResult
    from app.app.photos.services import AlbumService, MediaItemService
    from app.app.photos.services.media_item import (
        DownloadMediaItem,
        DownloadMediaItemSession,
        DownloadSessionInfo,
    )
    from app.toolkit.mediatypes import MediaType

    class IUseCaseServices(IAtomic, Protocol):
        album: AlbumService
        blob_metadata: BlobMetadataService
        blob_processor: BlobContentProcessor
        blob_thumbnailer: BlobThumbnailService
        media_item: MediaItemService

__all__ = [
    "MediaItemUseCase",
]


class MediaItemUseCase:
    __slots__ = [
        "_services",
        "album",
        "blob_metadata",
        "blob_processor",
        "media_item",
        "thumbnailer",
    ]

    def __init__(self, services: IUseCaseServices):
        self._services = services
        self.album = services.album
        self.blob_metadata = services.blob_metadata
        self.blob_processor = services.blob_processor
        self.media_item = services.media_item
        self.thumbnailer = services.blob_thumbnailer

    async def auto_add_category_batch(
        self,
        media_item_id: UUID,
        categories: Sequence[tuple[MediaItemCategoryName, int]],
    ) -> None:
        """
        Adds a set of categories provided by AI recognition.

        Raises:
            MediaItem.NotFound: If media item does not exist.
        """
        await self.media_item.auto_add_category_batch(
            media_item_id, categories=categories
        )

    async def count(self, owner_id: UUID) -> CountResult:
        """Returns total number of media items owner has."""
        return await self.media_item.count(owner_id)

    async def create_download_session(
        self, owner_id: UUID, media_item_ids: Sequence[UUID]
    ) -> DownloadSessionInfo:
        return await self.media_item.create_download_session(owner_id, media_item_ids)

    async def delete_batch(
        self, owner_id: UUID, ids: Sequence[UUID]
    ) -> list[MediaItem]:
        """Soft-deletes multiple media items at once."""
        async with self._services.atomic():
            items = await self.media_item.delete_batch(owner_id, ids)
            if item_ids := [item.id for item in items]:
                album_ids = await self.album.list_ids_by_cover_ids(owner_id, item_ids)
                await self.album.reassign_covers(album_ids)
            return items

    async def delete_immediately_batch(
        self, owner_id: UUID, ids: Sequence[UUID]
    ) -> None:
        """Permanently deletes multiple media items and their blobs."""
        items = await self.media_item.get_by_id_batch(ids)
        item_ids = [item.id for item in items if item.owner_id == owner_id]
        if item_ids:
            await self.media_item.delete_permanently(item_ids)

    def download(self, item: DownloadMediaItem) -> AsyncIterator[bytes]:
        return self.media_item.download(item)

    def download_batch(self, items: DownloadMediaItemSession) -> Iterable[bytes]:
        return self.media_item.download_batch(items)

    async def get_download_session(
        self, key: str
    ) -> DownloadMediaItemSession | None:
        return await self.media_item.get_download_session(key)

    async def get_content_metadata(
        self, owner_id: UUID, media_item_id: UUID
    ) -> BlobMetadata:
        """
        Returns content metadata for the specified owner's media item.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist for the owner.
            BlobMetadata.NotFound: If metadata does not exist for the backing blob.
        """
        item = await self.media_item.get_for_owner(owner_id, media_item_id)
        return await self.blob_metadata.get_by_blob_id(item.blob_id)

    async def list_(
        self, owner_id: UUID, *, only_favourites: bool = False, offset: int, limit: int
    ) -> list[MediaItem]:
        """Lists media items for a given owner."""
        return await self.media_item.list_(
            owner_id,
            only_favourites=only_favourites,
            offset=offset,
            limit=limit,
        )

    async def list_deleted(self, owner_id: UUID) -> list[MediaItem]:
        """Lists deleted media items."""
        return await self.media_item.list_deleted(owner_id, offset=0, limit=2_000)

    async def list_favourite_ids(self, user_id: UUID) -> list[UUID]:
        """Lists favourite media item IDs for the current user."""
        return await self.media_item.list_favourite_ids(user_id)

    async def list_categories(
        self, owner_id: UUID, media_item_id: UUID
    ) -> list[MediaItemCategory]:
        """
        Returns categories of the owner's MediaItem with given ID.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist.
        """
        item = await self.media_item.get_for_owner(owner_id, media_item_id)
        return await self.media_item.list_categories(item.id)

    async def mark_favourite_batch(
        self, user_id: UUID, ids: Sequence[UUID]
    ) -> None:
        """Marks multiple media items as favourite for the current user."""
        await self.media_item.mark_favourite_batch(user_id, ids)

    async def purge(self, owner_id: UUID) -> None:
        """Permanently deletes all deleted media items."""
        async for items in self.media_item.iter_deleted(owner_id):
            ids = [item.id for item in items]
            await self.media_item.delete_permanently(ids)

    async def restore_batch(
        self, owner_id: UUID, ids: Sequence[UUID]
    ) -> list[MediaItem]:
        """Restores multiple media items at once."""
        return await self.media_item.restore_batch(owner_id, ids)

    async def set_categories(
        self,
        owner_id: UUID,
        media_item_id: UUID,
        categories: Sequence[MediaItemCategoryName],
    ) -> None:
        """
        Clears existing and sets specified categories for MediaItem with given ID.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist.
        """
        item = await self.media_item.get_for_owner(owner_id, media_item_id)
        return await self.media_item.set_categories(item.id, categories)

    async def thumbnail(
        self, owner_id: UUID, media_item_id: UUID, size: int
    ) -> tuple[MediaItem, bytes, MediaType]:
        """
        Returns a thumbnail for the specified owner's media item.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist for the owner.
            Blob.ThumbnailUnavailable: If thumbnail can't be generated.
        """
        item = await self.media_item.get_for_owner(owner_id, media_item_id)
        thumbnail = await self.thumbnailer.thumbnail(item.blob_id, item.chash, size)
        return item, *thumbnail

    async def unmark_favourite_batch(
        self, user_id: UUID, ids: Sequence[UUID]
    ) -> None:
        """Removes favourite marks from multiple media items."""
        await self.media_item.unmark_favourite_batch(user_id, ids)

    async def upload(
        self,
        owner_id: UUID,
        name: str,
        content: IBlobContent,
        media_type: str,
    ) -> MediaItem:
        """Creates a new media item and schedules content processing."""
        item = await self.media_item.create(owner_id, name, content, media_type)
        await self.blob_processor.process_async(item.blob_id)
        return item
