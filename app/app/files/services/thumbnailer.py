from __future__ import annotations

import itertools
import os.path
from io import BytesIO
from typing import TYPE_CHECKING

from app.app.files.domain import File
from app.app.files.domain.content import InMemoryFileContent
from app.cache import cache
from app.config import config
from app.toolkit import mediatypes, thumbnails
from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from uuid import UUID

    from app.app.files.services.file import FileCoreService
    from app.app.infrastructure import IStorage

__all__ = ["ThumbnailService"]

_LOCK_KEY = "generate_thumbnails:{content_hash}:{size}"
_PREFIX = "thumbnails"


class ThumbnailService:
    __slots__ = ("filecore", "storage")

    def __init__(self, filecore: FileCoreService, storage: IStorage):
        self.filecore = filecore
        self.storage = storage

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

    async def delete_stale_thumbnails(self, chashes: Sequence[str]) -> None:
        """Cleanups thumbnails that don't have any reference."""
        items = {chash for chash in chashes if chash}
        items.difference_update(
            file.chash
            for file in await self.filecore.get_by_chash_batch(list(items))
        )

        to_delete = list(itertools.chain.from_iterable(
            (
                self.get_storage_key(chash, size)
                for size in config.features.pre_generated_thumbnail_sizes
            )
            for chash in items
        ))

        await self.storage.delete_batch(to_delete)

    async def generate_thumbnails(self, file_id: UUID, sizes: Iterable[int]) -> None:
        """Generates a set of thumbnails for the specified sizes."""
        file = await self.filecore.get_by_id(file_id)
        if file.size > config.features.max_file_size_to_thumbnail:
            return

        if not file.chash:
            return

        if not thumbnails.is_supported(file.mediatype):
            return

        content: BytesIO | None = None
        for size in sizes:
            path = self.get_storage_key(file.chash, size)
            lock_id = self._lock_id(file.chash, size)

            async with cache.lock(lock_id, expire=30, wait=True):
                if await self.storage.exists(path):
                    continue

                if not content:
                    _, chunks = await self.filecore.download(file_id)
                    content = BytesIO(b"".join([chunk async for chunk in chunks]))

                content.seek(0)
                try:
                    thumbnail, _ = await thumbnails.thumbnail(content, size=size)
                except thumbnails.ThumbnailUnavailable:
                    return

                await self.storage.makedirs(os.path.dirname(path))
                await self.storage.save(path, InMemoryFileContent(thumbnail))

    @cache.locked(key=_LOCK_KEY, ttl=30)
    async def thumbnail(
        self, file_id: UUID, content_hash: str, size: int
    ) -> tuple[bytes, MediaType]:
        """
        Returns a thumbnail for a given file ID. If thumbnail doesn't exist,
        it will be created and put to storage.

        Raises:
            File.IsADirectory: If file is a directory.
            File.NotFound: If file with this ID does not exist.
            File.ThumbnailUnavailable: If thumbnail can't be generated for a file.
        """
        path = self.get_storage_key(content_hash, size)
        if not content_hash:
            raise File.ThumbnailUnavailable() from None

        if await self.storage.exists(path):
            chunks = self.storage.download(path)
            thumb = b"".join([chunk async for chunk in chunks])
            return thumb, MediaType(mediatypes.guess(BytesIO(thumb)))

        file, chunks = await self.filecore.download(file_id)
        if file.size > config.features.max_file_size_to_thumbnail:
            raise File.ThumbnailUnavailable() from None

        content = BytesIO(b"".join([chunk async for chunk in chunks]))
        try:
            thumb, mediatype = await thumbnails.thumbnail(content, size=size)
        except thumbnails.ThumbnailUnavailable as exc:
            raise File.ThumbnailUnavailable() from exc

        await self.storage.makedirs(os.path.dirname(path))
        await self.storage.save(path, InMemoryFileContent(thumb))
        return thumb, mediatype
