from __future__ import annotations

import os.path
from io import BytesIO
from typing import TYPE_CHECKING

from app.app.files.domain import File
from app.app.files.domain.content import InMemoryFileContent
from app.cache import cache
from app.config import config

from . import thumbnails

if TYPE_CHECKING:
    from collections.abc import Iterable
    from uuid import UUID

    from app.app.files.services.file import FileCoreService
    from app.app.infrastructure import IStorage, IWorker

__all__ = ["ThumbnailService"]

_LOCK_KEY = "generate_thumbnails:{content_hash}:{size}"
_PREFIX = "thumbs"


class ThumbnailService:
    __slots__ = ("filecore", "storage", "worker")

    def __init__(self, filecore: FileCoreService, storage: IStorage, worker: IWorker):
        self.filecore = filecore
        self.storage = storage
        self.worker = worker

    @staticmethod
    def _lock_id(content_hash: str, size: int) -> str:
        return _LOCK_KEY.format(content_hash=content_hash, size=size)

    @staticmethod
    def _make_path(content_hash: str, size: int) -> str:
        parts = [
            content_hash[:2],
            content_hash[2:4],
            content_hash[4:6],
            f"{content_hash}_{size}.webp"
        ]
        return "/".join(parts)

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
            path = self._make_path(file.chash, size)
            lock_id = self._lock_id(file.chash, size)

            async with cache.lock(lock_id, expire=30, wait=True):
                if await self.storage.exists(_PREFIX, path):
                    continue

                if not content:
                    _, chunks = await self.filecore.download(file_id)
                    content = BytesIO(b"".join([chunk async for chunk in chunks]))

                content.seek(0)
                try:
                    thumbnail = await thumbnails.thumbnail(content, size=size)
                except File.ThumbnailUnavailable:
                    return

                await self.storage.makedirs(_PREFIX, os.path.dirname(path))
                await self.storage.save(_PREFIX, path, InMemoryFileContent(thumbnail))

    async def generate_thumbnails_async(
        self, file_id: UUID, sizes: Iterable[int]
    ) -> None:
        """Generates a set of thumbnails in a worker."""
        sizes = list(sizes)
        await self.worker.enqueue("generate_file_thumbnails", file_id, sizes)

    @cache.lock(_LOCK_KEY, expire=30)
    async def thumbnail(self, file_id: UUID, content_hash: str, size: int) -> bytes:
        """
        Returns a thumbnail for a given file ID. If thumbnail doesn't exist,
        it will be created and put to storage.

        Raises:
            File.IsADirectory: If file is a directory.
            File.NotFound: If file with this ID does not exist.
            File.ThumbnailUnavailable: If thumbnail can't be generated for a file.
        """
        path = self._make_path(content_hash, size)
        if not content_hash:
            raise File.ThumbnailUnavailable() from None

        if await self.storage.exists(_PREFIX, path):
            chunks = self.storage.download(_PREFIX, path)
            return b"".join([chunk async for chunk in chunks])

        file, chunks = await self.filecore.download(file_id)
        if file.size > config.features.max_file_size_to_thumbnail:
            raise File.ThumbnailUnavailable() from None

        content = BytesIO(b"".join([chunk async for chunk in chunks]))
        thumb = await thumbnails.thumbnail(content, size=size)
        await self.storage.makedirs(_PREFIX, os.path.dirname(path))
        await self.storage.save(_PREFIX, path, InMemoryFileContent(thumb))
        return thumb
