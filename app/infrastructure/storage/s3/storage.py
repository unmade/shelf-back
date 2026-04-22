from __future__ import annotations

import asyncio
import os
import os.path
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Self

import stream_zip

from app.app.files.domain import File
from app.app.infrastructure.storage import IStorage, StorageFile
from app.infrastructure.storage._datastructures import StreamZipFile

from .clients import (
    AsyncS3Client,
    S3Client,
    S3ClientConfig,
)
from .clients.exceptions import NoSuchKey, ResourceNotFound

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Collection, Iterable, Iterator

    from app.app.blobs.domain import IBlobContent
    from app.app.infrastructure.storage import DownloadBatchItem
    from app.config import S3StorageConfig

__all__ = ["S3Storage"]


class S3Storage(IStorage):
    __slots__ = ("location", "bucket", "s3", "sync_s3", "_stack")

    def __init__(self, config: S3StorageConfig):
        self.location = str(config.s3_location)
        self.bucket = config.s3_bucket

        s3_client_config = S3ClientConfig(
            base_url=str(config.s3_location),
            access_key=config.s3_access_key_id,
            secret_key=config.s3_secret_access_key,
            region=config.s3_region,
        )
        self.s3 = AsyncS3Client(s3_client_config)
        self.sync_s3 = S3Client(s3_client_config)

        self._stack = AsyncExitStack()

    async def __aenter__(self) -> Self:
        await self._stack.enter_async_context(self.s3)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._stack.aclose()

    @staticmethod
    def _has_path(target: str, paths: Collection[str] | None) -> bool:
        if paths is None:
            return True

        target = target.lower()
        haystack = {p.lower() for p in paths}
        if target in haystack:
            return True

        return any(target.startswith(prefix) for prefix in haystack)

    async def delete(self, key: str) -> None:
        key = os.path.normpath(key)
        await self.s3.delete(self.bucket, key)

    async def delete_batch(self, keys: Iterable[str]) -> None:
        normalized = [os.path.normpath(k) for k in keys]
        await self.s3.delete(self.bucket, *normalized)

    async def deletedir(self, key: str) -> None:
        prefix = f"{os.path.normpath(key)}/"
        await self.s3.delete_recursive(self.bucket, prefix)

    async def emptydir(self, key: str) -> None:
        await self.deletedir(key)

    async def exists(self, key: str) -> bool:
        key = os.path.normpath(key)
        try:
            await self.s3.head_object(self.bucket, key)
        except ResourceNotFound:
            return False
        return True

    async def download(self, key: str) -> AsyncIterator[bytes]:
        key = os.path.normpath(key)
        try:
            async for chunk in self.s3.iter_download(self.bucket, key):
                yield chunk
        except NoSuchKey as exc:
            raise File.NotFound() from exc

    def download_batch(self, items: Iterable[DownloadBatchItem]) -> Iterable[bytes]:
        return stream_zip.stream_zip(
            self._download_batch_iter(items)
        )

    def _download_batch_iter(
        self, items: Iterable[DownloadBatchItem]
    ) -> Iterator[StreamZipFile]:
        for item in items:
            key = os.path.normpath(item.key)
            filename = item.archive_path or os.path.basename(key)
            if item.is_dir:
                yield from self._downloaddir_iter(key, prefix=filename)
            else:
                entry = self.sync_s3.head_object(self.bucket, key)
                yield StreamZipFile(
                    path=filename,
                    modified_at=entry.last_modified,
                    perms=0o600,
                    compression=stream_zip.ZIP_32,
                    content=self.sync_s3.iter_download(self.bucket, entry.key),
                )

    def downloaddir(
        self,
        key: str,
        include_keys: Collection[str] | None = None,
    ) -> Iterable[bytes]:
        key = os.path.normpath(key)
        return stream_zip.stream_zip(
            self._downloaddir_iter(key, include_keys=include_keys)
        )

    def _downloaddir_iter(
        self,
        key: str,
        prefix: str = "",
        include_keys: Collection[str] | None = None,
    ) -> Iterator[StreamZipFile]:
        for entry in self.sync_s3.list_objects(self.bucket, key):
            if self._has_path(entry.key, include_keys):
                yield StreamZipFile(
                    path=os.path.join(
                        prefix,
                        os.path.relpath(entry.key, key),
                    ),
                    modified_at=entry.last_modified,
                    perms=0o600,
                    compression=stream_zip.ZIP_32,
                    content=self.sync_s3.iter_download(self.bucket, entry.key),
                )

    async def iterdir(self, key: str) -> AsyncIterator[StorageFile]:
        prefix = f"{os.path.normpath(key)}/"
        async for item in self.s3.list_objects(self.bucket, prefix, delimiter="/"):
            if isinstance(item, str):
                stripped = item.strip("/")
                yield StorageFile(
                    name=os.path.basename(stripped),
                    path=stripped,
                    size=0,
                    mtime=0,
                    is_dir=True,
                )
            else:
                yield StorageFile(
                    name=os.path.basename(item.key),
                    path=item.key,
                    size=item.size,
                    mtime=item.last_modified.timestamp(),
                    is_dir=False,
                )

    async def makedirs(self, key: str) -> None:
        return None

    async def move(self, at: str, to: str) -> None:
        from_key = os.path.normpath(at)
        to_key = os.path.normpath(to)
        try:
            await self.s3.copy_object(self.bucket, from_key, to_key)
        except NoSuchKey as exc:
            raise File.NotFound() from exc
        await self.s3.delete(self.bucket, from_key)

    async def movedir(self, at: str, to: str) -> None:
        from_prefix = f"{os.path.normpath(at)}/"
        to_prefix = f"{os.path.normpath(to)}/"
        keys_to_delete = []
        async with asyncio.TaskGroup() as tg:
            async for entry in self.s3.list_objects(self.bucket, from_prefix):
                rel_key = os.path.relpath(entry.key, from_prefix)
                new_key = os.path.normpath(os.path.join(to_prefix, rel_key))
                keys_to_delete.append(entry.key)
                tg.create_task(
                    self.s3.copy_object(self.bucket, entry.key, new_key)
                )
        await self.s3.delete(self.bucket, *keys_to_delete)

    async def save(self, key: str, content: IBlobContent) -> StorageFile:
        key = os.path.normpath(key)
        file = await self.s3.upload_obj(self.bucket, key, content)
        return StorageFile(
            name=os.path.basename(key),
            path=key,
            size=file.size,
            mtime=file.last_modified.timestamp(),
            is_dir=False,
        )
