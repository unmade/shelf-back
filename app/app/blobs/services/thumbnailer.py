from __future__ import annotations

import os.path
from io import BytesIO
from typing import IO, TYPE_CHECKING

from app.app.blobs.domain import Blob
from app.app.blobs.domain.content import InMemoryBlobContent
from app.cache import cache
from app.toolkit import mediatypes, thumbnails
from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from collections.abc import Iterable
    from uuid import UUID

    from app.app.blobs.services.blob import BlobService
    from app.app.infrastructure import IStorage

__all__ = ["BlobThumbnailService"]

_LOCK_KEY = "generate_thumbnails:{content_hash}:{size}"
_PREFIX = "thumbnails"


class BlobThumbnailService:
    __slots__ = ("blob_service", "storage", "max_file_size")

    def __init__(
        self,
        blob_service: BlobService,
        storage: IStorage,
        max_file_size: int,
    ) -> None:
        self.blob_service = blob_service
        self.storage = storage
        self.max_file_size = max_file_size

    @staticmethod
    def _lock_id(content_hash: str, size: int) -> str:
        return _LOCK_KEY.format(content_hash=content_hash, size=size)

    @staticmethod
    def is_supported(mediatype: str) -> bool:
        """True if thumbnail available for a given mediatype, otherwise False."""
        return thumbnails.is_supported(mediatype)

    @staticmethod
    def get_storage_key(content_hash: str, size: int) -> str:
        parts = [
            _PREFIX,
            content_hash[:2],
            content_hash[2:4],
            content_hash[4:6],
            f"{content_hash}_{size}.webp"
        ]
        return os.path.join(*parts)

    async def generate(
        self, chash: str, content: IO[bytes], sizes: Iterable[int]
    ) -> None:
        """Generates a set of thumbnails for the specified sizes."""
        content_size = content.seek(0, os.SEEK_END)
        if content_size > self.max_file_size:
            return

        content.seek(0)
        media_type = mediatypes.guess(content)
        if not thumbnails.is_supported(media_type):
            return

        if not chash:
            return

        for size in sizes:
            path = self.get_storage_key(chash, size)
            lock_id = self._lock_id(chash, size)

            async with cache.lock(lock_id, expire=30, wait=True):
                if await self.storage.exists(path):
                    continue

                content.seek(0)
                try:
                    thumbnail, _ = await thumbnails.thumbnail(content, size=size)
                except thumbnails.ThumbnailUnavailable:
                    return

                await self.storage.makedirs(os.path.dirname(path))
                await self.storage.save(path, InMemoryBlobContent(thumbnail))

    @cache.locked(key=_LOCK_KEY, ttl=30)
    async def thumbnail(
        self, blob_id: UUID, content_hash: str, size: int
    ) -> tuple[bytes, MediaType]:
        """
        Returns a thumbnail for a given blob ID. If thumbnail doesn't exist,
        it will be created and put to storage.

        Raises:
            Blob.NotFound: If blob with this ID does not exist.
            Blob.ThumbnailUnavailable: If thumbnail can't be generated for a blob.
        """

        storage_key = self.get_storage_key(content_hash, size)
        if not content_hash:
            raise Blob.ThumbnailUnavailable() from None

        if await self.storage.exists(storage_key):
            chunks = self.storage.download(storage_key)
            thumb = b"".join([chunk async for chunk in chunks])
            return thumb, MediaType(mediatypes.guess(BytesIO(thumb)))

        blob = await self.blob_service.get_by_id(blob_id)
        if blob.size > self.max_file_size:
            raise Blob.ThumbnailUnavailable() from None

        chunks = self.blob_service.download(blob.storage_key)
        content = BytesIO(b"".join([chunk async for chunk in chunks]))
        try:
            thumb, mediatype = await thumbnails.thumbnail(content, size=size)
        except thumbnails.ThumbnailUnavailable as exc:
            raise Blob.ThumbnailUnavailable() from exc

        await self.storage.makedirs(os.path.dirname(storage_key))
        await self.storage.save(storage_key, InMemoryBlobContent(thumb))
        return thumb, mediatype
