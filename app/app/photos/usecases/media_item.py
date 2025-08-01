from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Protocol

from app.app.files.services.file.filecore import DownloadBatchItem
from app.app.photos.domain import MediaItem
from app.cache import cache
from app.config import config

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from uuid import UUID

    from app.app.files.domain import AnyFile, SharedLink
    from app.app.files.services import NamespaceService, SharingService
    from app.app.files.services.file import FileCoreService
    from app.app.photos.domain.media_item import (
        MediaItemCategory,
        MediaItemCategoryName,
    )
    from app.app.photos.repositories.media_item import CountResult
    from app.app.photos.services import MediaItemService

    class IUseCaseServices(Protocol):
        filecore: FileCoreService
        media_item: MediaItemService
        namespace: NamespaceService
        sharing: SharingService

__all__ = [
    "MediaItemUseCase",
]

_DOWNLOAD_CACHE_PREFIX = "media_item:batch"

type DownloadBatchSession = list[DownloadBatchItem]


class MediaItemUseCase:
    __slots__ = ["_services", "filecore", "media_item", "namespace", "sharing"]

    def __init__(self, services: IUseCaseServices):
        self._services = services
        self.filecore = services.filecore
        self.media_item = services.media_item
        self.namespace = services.namespace
        self.sharing = services.sharing

    @staticmethod
    def _is_file_a_media_item(file: AnyFile) -> bool:
        library_path = config.features.photos_library_path
        return (
            file.path.is_relative_to(library_path)
            and file.mediatype in MediaItem.ALLOWED_MEDIA_TYPES
        )

    async def auto_add_category_batch(
        self, file_id: UUID, categories: Sequence[tuple[MediaItemCategoryName, int]]
    ) -> None:
        """
        Adds a set of categories provided by AI recognition.

        Raises:
            MediaItem.NotFound: If media item with a given `file_id` does not exist.
        """
        await self.media_item.auto_add_category_batch(file_id, categories=categories)

    async def count(self, user_id: UUID) -> CountResult:
        """Returns total number of media items user has."""
        return await self.media_item.count(user_id)

    async def delete_batch(
        self, user_id: UUID, file_ids: Sequence[UUID]
    ) -> list[MediaItem]:
        """Deletes multiple media items at once."""
        return await self.media_item.delete_batch(user_id, file_ids)

    async def delete_immediately_batch(
        self, user_id: UUID, file_ids: Sequence[UUID]
    ) -> None:
        """Deletes multiple media items permanently."""
        namespace = await self.namespace.get_by_owner_id(user_id)
        files = await self.filecore.get_by_id_batch(file_ids)
        paths = [file.path for file in files]
        await self.filecore.delete_batch(namespace.path, paths)

    def download_batch(self, items: DownloadBatchSession) -> Iterable[bytes]:
        return self.filecore.download_batch(items)

    async def download_batch_create_session(
        self, user_id: UUID, file_ids: Sequence[UUID]
    ) -> str:
        namespace = await self.namespace.get_by_owner_id(user_id)
        files = [
            DownloadBatchItem(
                ns_path=file.ns_path,
                path=file.path,
                is_dir=file.is_folder(),
            )
            for file in await self.filecore.get_by_id_batch(file_ids)
            if file.ns_path == namespace.path and self._is_file_a_media_item(file)
        ]
        key = secrets.token_urlsafe()
        await cache.set(key=f"{_DOWNLOAD_CACHE_PREFIX}:{key}", value=files, expire=60)
        return key

    async def download_batch_get_session(self, key: str) -> DownloadBatchSession | None:
        key = f"{_DOWNLOAD_CACHE_PREFIX}:{key}"
        value: DownloadBatchSession | None = await cache.get(key)
        if value is None:
            return None
        await cache.delete(key)
        return value

    async def list_(
        self, user_id: UUID, *, only_favourites: bool = False, offset: int, limit: int
    ) -> list[MediaItem]:
        """Lists media items for a given user."""
        return await self.media_item.list_(
            user_id,
            only_favourites=only_favourites,
            offset=offset,
            limit=limit,
        )

    async def list_deleted(self, user_id: UUID) -> list[MediaItem]:
        """Lists deleted media items."""
        return await self.media_item.list_deleted(user_id, offset=0, limit=2_000)

    async def list_categories(
        self, user_id: UUID, file_id: UUID
    ) -> list[MediaItemCategory]:
        """
        Returns categories of the user MediaItem with given ID.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist.
        """
        item = await self.media_item.get_for_user(user_id, file_id)
        return await self.media_item.list_categories(item.file_id)

    async def list_shared_links(
        self, user_id: UUID
    ) -> list[tuple[MediaItem, SharedLink]]:
        """Lists shared links."""
        namespace = await self.namespace.get_by_owner_id(user_id)
        links = await self.sharing.list_links_by_ns(namespace.path, limit=1000)
        file_ids = [link.file_id for link in links]
        items_by_id = {
            item.file_id: item
            for item in await self.media_item.get_by_id_batch(file_ids)
        }
        return [
            (item, link)
            for link in links
            if (item := items_by_id.get(link.file_id))
        ]

    async def purge(self, user_id: UUID) -> None:
        """Permanently deletes all deleted media items."""
        namespace = await self.namespace.get_by_owner_id(user_id)
        async for items in self.media_item.iter_deleted(user_id):
            file_ids = [item.file_id for item in items]
            files = await self.filecore.get_by_id_batch(file_ids)
            paths = [file.path for file in files]
            await self.filecore.delete_batch(namespace.path, paths)

    async def restore_batch(
        self, user_id: UUID, file_ids: Sequence[UUID]
    ) -> list[MediaItem]:
        """Restores multiple media items at once."""
        return await self.media_item.restore_batch(user_id, file_ids)

    async def set_categories(
        self, user_id: UUID, file_id: UUID, categories: Sequence[MediaItemCategoryName]
    ) -> None:
        """
        Clears existing and sets specified categories for MediaItem with given file ID.

        Raises:
            MediaItem.NotFound: If MediaItem does not exist.
        """
        item = await self.media_item.get_for_user(user_id, file_id)
        return await self.media_item.set_categories(item.file_id, categories)
