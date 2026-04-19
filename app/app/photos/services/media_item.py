from __future__ import annotations

import secrets
import uuid
from collections.abc import AsyncIterator, Iterable, Sequence
from datetime import datetime
from typing import TYPE_CHECKING, NamedTuple, Protocol

from app.app.infrastructure.database import SENTINEL_ID
from app.app.infrastructure.storage import DownloadBatchItem
from app.app.photos.domain import MediaItem
from app.cache import cache
from app.toolkit import timezone

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.blobs.domain import IBlobContent
    from app.app.blobs.services import BlobService
    from app.app.infrastructure.database import IDatabase
    from app.app.photos.domain.media_item import (
        MediaItemCategory,
        MediaItemCategoryName,
    )
    from app.app.photos.repositories import (
        IMediaItemFavouriteRepository,
        IMediaItemRepository,
    )
    from app.app.photos.repositories.media_item import CountResult

    class IServiceDatabase(IDatabase, Protocol):
        media_item: IMediaItemRepository
        media_item_favourite: IMediaItemFavouriteRepository

__all__ = ["MediaItemService"]


_DOWNLOAD_CACHE_PREFIX = "photos:media_item:download"


class DownloadMediaItem(NamedTuple):
    storage_key: str
    name: str
    media_type: str
    size: int
    modified_at: datetime


class DownloadSessionInfo(NamedTuple):
    key: str
    items_count: int


type DownloadMediaItemSession = tuple[DownloadMediaItem, ...]


def _make_storage_key(owner_id: UUID, name: str) -> str:
    now = timezone.now()
    prefix = uuid.uuid7().hex[-8:]
    return f"{owner_id}/photos/{now:%Y}/{now:%m}/{now:%d}/{prefix}_{name}"


class MediaItemService:
    __slots__ = ["blob_service", "db"]

    def __init__(
        self, database: IServiceDatabase, blob_service: BlobService
    ):
        self.db = database
        self.blob_service = blob_service

    async def _get_download_items(
        self, owner_id: UUID, media_item_ids: Sequence[UUID]
    ) -> DownloadMediaItemSession:
        """Returns downloadable blob-backed items for the owner."""
        item_ids = list(dict.fromkeys(media_item_ids))
        items = [
            item
            for item in await self.db.media_item.get_by_id_batch(item_ids)
            if item.owner_id == owner_id
        ]
        if not items:
            raise MediaItem.NotFound()

        blobs = await self.blob_service.get_by_id_batch(
            [item.blob_id for item in items]
        )
        blobs_by_id = {blob.id: blob for blob in blobs}
        result = []
        for item in items:
            blob = blobs_by_id.get(item.blob_id)
            if blob is None:
                continue
            result.append(
                DownloadMediaItem(
                    storage_key=blob.storage_key,
                    name=item.name,
                    media_type=item.media_type,
                    size=item.size,
                    modified_at=item.modified_at,
                )
            )

        if not result:
            raise MediaItem.NotFound()
        return tuple(result)

    async def auto_add_category_batch(
        self,
        media_item_id: UUID,
        categories: Sequence[tuple[MediaItemCategoryName, int]],
    ) -> None:
        """
        Adds a set of AI-recognized categories.

        Raises:
            MediaItem.NotFound: If media item does not exist.
        """
        await self.db.media_item.add_category_batch(
            media_item_id,
            categories=[
                MediaItem.Category(
                    name=name,
                    origin=MediaItem.Category.Origin.AUTO,
                    probability=probability,
                )
                for name, probability in categories
            ]
        )

    async def count(self, owner_id: UUID) -> CountResult:
        """Returns total number of media items owner with specified ID has."""
        return await self.db.media_item.count(owner_id)

    async def create(
        self,
        owner_id: UUID,
        name: str,
        content: IBlobContent,
        media_type: str,
    ) -> MediaItem:
        """Creates a new media item backed by a Blob."""
        storage_key = _make_storage_key(owner_id, name)
        blob = await self.blob_service.create(storage_key, content, media_type)

        now = timezone.now()
        item = MediaItem(
            id=SENTINEL_ID,
            owner_id=owner_id,
            blob_id=blob.id,
            name=name,
            media_type=blob.media_type,
            size=blob.size,
            chash=blob.chash,
            created_at=now,
            modified_at=now,
        )
        return await self.db.media_item.save(item)

    async def create_download_session(
        self, owner_id: UUID, media_item_ids: Sequence[UUID]
    ) -> DownloadSessionInfo:
        items = await self._get_download_items(owner_id, media_item_ids)
        if not items:
            raise MediaItem.NotFound()

        key = secrets.token_urlsafe()
        await cache.set(
            key=f"{_DOWNLOAD_CACHE_PREFIX}:{key}",
            value=items,
            expire=60,
        )
        return DownloadSessionInfo(key=key, items_count=len(items))

    async def delete_batch(
        self, owner_id: UUID, ids: Sequence[UUID]
    ) -> list[MediaItem]:
        """Soft-deletes multiple media items at once."""
        deleted_at = timezone.now()
        return await self.db.media_item.set_deleted_at_batch(
            owner_id, ids, deleted_at=deleted_at
        )

    async def delete_permanently(self, ids: Sequence[UUID]) -> None:
        """Permanently deletes media items and their backing blobs."""
        items = await self.db.media_item.get_by_id_batch(ids)
        blob_ids = [item.blob_id for item in items]
        await self.db.media_item.delete_batch(ids)
        await self.blob_service.delete_batch(blob_ids)

    def download(self, item: DownloadMediaItem) -> AsyncIterator[bytes]:
        return self.blob_service.download(item.storage_key)

    def download_batch(self, items: DownloadMediaItemSession) -> Iterable[bytes]:
        return self.blob_service.download_batch([
            DownloadBatchItem(
                key=item.storage_key,
                is_dir=False,
                archive_path=item.name,
            )
            for item in items
        ])

    async def get_by_id_batch(self, media_item_ids: Sequence[UUID]) -> list[MediaItem]:
        """Returns all media items with target IDs."""
        return await self.db.media_item.get_by_id_batch(media_item_ids)

    async def get_download_session(
        self, key: str
    ) -> DownloadMediaItemSession | None:
        cache_key = f"{_DOWNLOAD_CACHE_PREFIX}:{key}"
        value: DownloadMediaItemSession | None = await cache.get(cache_key)
        if value is None:
            return None
        await cache.delete(cache_key)
        return value

    async def get_for_owner(self, owner_id: UUID, media_item_id: UUID) -> MediaItem:
        """
        Gets MediaItem with given ID for the specified owner.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist for the specified owner.
        """
        return await self.db.media_item.get_for_owner(owner_id, media_item_id)

    async def iter_deleted(
        self, owner_id: UUID, *, batch_size: int = 1000
    ) -> AsyncIterator[list[MediaItem]]:
        """Iterates through all deleted media items in batches."""
        limit = batch_size
        offset = -limit

        while True:
            offset += limit
            items = await self.db.media_item.list_deleted(
                owner_id,
                offset=offset,
                limit=limit,
            )
            if not items:
                return
            yield items

    async def list_(
        self, owner_id: UUID, *, only_favourites: bool = False, offset: int, limit: int
    ) -> list[MediaItem]:
        """Lists media items for a given owner."""
        return await self.db.media_item.list_by_owner(
            owner_id, only_favourites=only_favourites, offset=offset, limit=limit
        )

    async def list_categories(self, media_item_id: UUID) -> list[MediaItemCategory]:
        """
        Return categories of the MediaItem with specified ID.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist.
        """
        return await self.db.media_item.list_categories(media_item_id)

    async def list_deleted(
        self, owner_id: UUID, *, offset: int, limit: int = 25
    ) -> list[MediaItem]:
        """Lists owner's deleted media items."""
        return await self.db.media_item.list_deleted(
            owner_id, offset=offset, limit=limit
        )

    async def list_favourite_ids(self, user_id: UUID) -> list[UUID]:
        """Lists favourite media item IDs for the specified user."""
        return await self.db.media_item_favourite.list_ids(user_id)

    async def mark_favourite_batch(
        self, user_id: UUID, media_item_ids: Sequence[UUID]
    ) -> None:
        """Marks currently accessible media items as favourite for the user."""
        items = await self.db.media_item.get_by_id_batch(media_item_ids)
        accessible_ids = [item.id for item in items if item.owner_id == user_id]
        if not accessible_ids:
            return
        await self.db.media_item_favourite.add_batch(user_id, accessible_ids)

    async def restore_batch(
        self, owner_id: UUID, ids: Sequence[UUID]
    ) -> list[MediaItem]:
        """Restores multiple media items at once."""
        deleted_at = None
        return await self.db.media_item.set_deleted_at_batch(
            owner_id, ids, deleted_at=deleted_at
        )

    async def unmark_favourite_batch(
        self, user_id: UUID, media_item_ids: Sequence[UUID]
    ) -> None:
        """Removes favourite marks from multiple media items."""
        await self.db.media_item_favourite.remove_batch(user_id, media_item_ids)

    async def set_categories(
        self, media_item_id: UUID, categories: Sequence[MediaItemCategoryName]
    ) -> None:
        """
        Clears existing and sets specified categories for MediaItem with given ID.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist.
        """
        await self.db.media_item.set_categories(
            media_item_id,
            categories=[
                MediaItem.Category(
                    name=category,
                    origin=MediaItem.Category.Origin.USER,
                    probability=100,
                )
                for category in categories
            ]
        )
