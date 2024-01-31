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
    from collections.abc import AsyncIterator, Iterable, Iterator

    from app.app.files.domain import AnyPath, IFileContent
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

    def _joinpath(self, ns_path: AnyPath, path: AnyPath) -> str:
        return os.path.normpath(os.path.join(str(ns_path), str(path)))

    async def delete(self, ns_path: AnyPath, path: AnyPath) -> None:
        key = self._joinpath(ns_path, path)
        await self.s3.delete(self.bucket, key)

    async def delete_batch(self, items: Iterable[tuple[AnyPath, AnyPath]]) -> None:
        keys = [self._joinpath(ns_path, path) for ns_path, path in items]
        await self.s3.delete(self.bucket, *keys)

    async def deletedir(self, ns_path: AnyPath, path: AnyPath) -> None:
        prefix = f"{self._joinpath(ns_path, path)}/"
        await self.s3.delete_recursive(self.bucket, prefix)

    async def emptydir(self, ns_path: AnyPath, path: AnyPath) -> None:
        await self.deletedir(ns_path, path)

    async def exists(self, ns_path: AnyPath, path: AnyPath) -> bool:
        key = self._joinpath(ns_path, path)
        try:
            await self.s3.head_object(self.bucket, key)
        except ResourceNotFound:
            return False
        return True

    async def download(self, ns_path: AnyPath, path: AnyPath) -> AsyncIterator[bytes]:
        key = self._joinpath(ns_path, path)
        try:
            async for chunk in self.s3.iter_download(self.bucket, key):
                yield chunk
        except NoSuchKey as exc:
            raise File.NotFound() from exc

    def downloaddir(self, ns_path: AnyPath, path: AnyPath) -> Iterator[bytes]:
        prefix = self._joinpath(ns_path, path)
        return stream_zip.stream_zip(  # type: ignore[no-any-return]
            StreamZipFile(
                path=os.path.relpath(entry.key, prefix),
                modified_at=entry.last_modified,
                perms=0o600,
                compression=stream_zip.ZIP_32,
                content=self.sync_s3.iter_download(self.bucket, entry.key),
            )
            for entry in self.sync_s3.list_objects(self.bucket, prefix)
        )

    async def iterdir(
        self, ns_path: AnyPath, path: AnyPath
    ) -> AsyncIterator[StorageFile]:
        ns_path = str(ns_path)
        prefix = f"{self._joinpath(ns_path, path)}/"
        async for item in self.s3.list_objects(self.bucket, prefix, delimiter="/"):
            if isinstance(item, str):
                key = item.strip("/")
                yield StorageFile(
                    name=os.path.basename(key),
                    ns_path=ns_path,
                    path=key[len(ns_path) + 1:],
                    size=0,
                    mtime=0,
                    is_dir=True,
                )
            else:
                yield StorageFile(
                    name=os.path.basename(item.key),
                    ns_path=ns_path,
                    path=item.key[len(ns_path) + 1:],
                    size=item.size,
                    mtime=item.last_modified.timestamp(),
                    is_dir=False,
                )

    async def makedirs(self, ns_path: AnyPath, path: AnyPath) -> None:
        return None

    async def move(
        self, at: tuple[AnyPath, AnyPath], to: tuple[AnyPath, AnyPath]
    ) -> None:
        from_key = self._joinpath(*at)
        to_key = self._joinpath(*to)
        try:
            await self.s3.copy_object(self.bucket, from_key, to_key)
        except NoSuchKey as exc:
            raise File.NotFound() from exc
        await self.s3.delete(self.bucket, from_key)

    async def movedir(
        self, at: tuple[AnyPath, AnyPath], to: tuple[AnyPath, AnyPath]
    ) -> None:
        from_prefix = f"{self._joinpath(*at)}/"
        to_prefix = f"{self._joinpath(*to)}/"
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

    async def save(
        self,
        ns_path: AnyPath,
        path: AnyPath,
        content: IFileContent,
    ) -> StorageFile:
        key = self._joinpath(ns_path, path)
        file = await self.s3.upload_obj(self.bucket, key, content)
        return StorageFile(
            name=os.path.basename(str(path)),
            ns_path=str(ns_path),
            path=str(path),
            size=file.size,
            mtime=file.last_modified.timestamp(),
            is_dir=False,
        )
