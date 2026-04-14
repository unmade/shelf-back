from __future__ import annotations

import asyncio
import contextlib
import datetime
import glob
import os
import os.path
import shutil
from typing import TYPE_CHECKING, Self

import stream_zip

from app.app.files.domain import File
from app.app.infrastructure.storage import IStorage, StorageFile
from app.config import FileSystemStorageConfig

from ._datastructures import StreamZipFile

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Collection, Iterable, Iterator

    from app.app.files.domain import IFileContent
    from app.app.infrastructure.storage import DownloadBatchItem

__all__ = ["FileSystemStorage"]


class FileSystemStorage(IStorage):
    __slots__ = ("location",)

    def __init__(self, config: FileSystemStorageConfig):
        self.location = config.fs_location

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    @staticmethod
    def _has_path(target: str, paths: Collection[str] | None) -> bool:
        if paths is None:
            return True

        target = target.lower()
        haystack = {p.lower() for p in paths}
        if target in haystack:
            return True

        return any(target.startswith(prefix) for prefix in haystack)

    def _fullpath(self, key: str) -> str:
        """Return the full normalized path for a storage key."""
        return os.path.normpath(os.path.join(self.location, key))

    def _from_entry(self, entry: os.DirEntry[str]) -> StorageFile:
        stat = entry.stat()
        return StorageFile(
            name=entry.name,
            path=entry.path[len(self.location) + 1:],
            size=stat.st_size,
            mtime=stat.st_mtime,
            is_dir=entry.is_dir(),
        )

    def _from_path(self, path: str) -> StorageFile:
        stat = os.lstat(path)
        return StorageFile(
            name=os.path.basename(path),
            path=path[len(self.location) + 1:],
            size=stat.st_size,
            mtime=stat.st_mtime,
            is_dir=os.path.isdir(path),
        )

    async def delete(self, key: str) -> None:
        fullpath = self._fullpath(key)
        if not os.path.isdir(fullpath):
            with contextlib.suppress(FileNotFoundError):
                await asyncio.to_thread(os.unlink, fullpath)

    async def delete_batch(self, keys: Iterable[str]) -> None:
        for key in keys:
            await self.delete(key)

    async def deletedir(self, key: str) -> None:
        fullpath = self._fullpath(key)
        with contextlib.suppress(FileNotFoundError, NotADirectoryError):
            await asyncio.to_thread(shutil.rmtree, fullpath)

    async def emptydir(self, key: str) -> None:
        fullpath = self._fullpath(key)
        async with asyncio.TaskGroup() as tg:
            with contextlib.suppress(FileNotFoundError, NotADirectoryError):
                for entry in await asyncio.to_thread(os.scandir, fullpath):
                    if entry.is_dir():
                        tg.create_task(asyncio.to_thread(shutil.rmtree, entry.path))
                    else:
                        tg.create_task(asyncio.to_thread(os.unlink, entry.path))

    async def download(self, key: str) -> AsyncIterator[bytes]:
        fullpath = self._fullpath(key)

        try:
            file = self._from_path(fullpath)
        except FileNotFoundError as exc:
            raise File.NotFound() from exc

        if file.is_dir():
            raise File.NotFound()

        with open(fullpath, "rb", buffering=4096) as f:
            for chunk in f:
                yield chunk

    def download_batch(self, items: Iterable[DownloadBatchItem]) -> Iterable[bytes]:
        return stream_zip.stream_zip(
            self._download_batch_iter(items)
        )

    def _download_batch_iter(
        self, items: Iterable[DownloadBatchItem]
    ) -> Iterator[StreamZipFile]:
        for key, _ in items:
            fullpath = self._fullpath(key)
            file = self._from_path(fullpath)
            if file.is_dir():
                yield from self._downloaddir_iter(key, prefix=file.name)
            else:
                with open(fullpath, "rb") as content:
                    yield StreamZipFile(
                        path=file.name,
                        modified_at=datetime.datetime.fromtimestamp(file.mtime),
                        perms=0o600,
                        compression=stream_zip.ZIP_32,
                        content=content,
                    )

    def downloaddir(
        self,
        key: str,
        include_keys: Collection[str] | None = None,
    ) -> Iterable[bytes]:
        return stream_zip.stream_zip(
            self._downloaddir_iter(key, include_keys=include_keys)
        )

    def _downloaddir_iter(
        self,
        key: str,
        prefix: str = "",
        include_keys: Collection[str] | None = None,
    ) -> Iterator[StreamZipFile]:
        fullpath = self._fullpath(key)
        pathnames = glob.iglob(
            os.path.normpath(os.path.join(fullpath, "**/*")), recursive=True,
        )
        for pathname in pathnames:
            file = self._from_path(pathname)
            if file.is_dir():
                continue

            if not self._has_path(file.path, include_keys):
                continue

            with open(pathname, "rb") as content:
                yield StreamZipFile(
                    path=os.path.join(
                        prefix,
                        os.path.relpath(file.path, key),
                    ),
                    modified_at=datetime.datetime.fromtimestamp(file.mtime),
                    perms=0o600,
                    compression=stream_zip.ZIP_32,
                    content=content,
                )

    async def exists(self, key: str) -> bool:
        fullpath = self._fullpath(key)
        return os.path.exists(fullpath)

    async def iterdir(self, key: str) -> AsyncIterator[StorageFile]:
        dir_path = self._fullpath(key)
        try:
            entries = await asyncio.to_thread(os.scandir, dir_path)
        except FileNotFoundError as exc:
            raise File.NotFound() from exc
        except NotADirectoryError as exc:
            raise File.NotADirectory() from exc

        for entry in entries:
            try:
                yield self._from_entry(entry)
            except FileNotFoundError:
                if entry.is_symlink():
                    continue
                raise  # pragma: no cover

    async def makedirs(self, key: str) -> None:
        self._makedirs(key)

    def _makedirs(self, key: str) -> None:
        fullpath = self._fullpath(key)
        try:
            os.makedirs(fullpath, exist_ok=True)
        except FileExistsError as exc:
            raise File.AlreadyExists() from exc
        except NotADirectoryError as exc:
            raise File.NotADirectory() from exc

    async def move(self, at: str, to: str) -> None:
        from_fullpath = self._fullpath(at)
        to_fullpath = self._fullpath(to)
        if os.path.isdir(from_fullpath):
            raise File.NotFound() from None

        parent = os.path.dirname(to_fullpath)
        if not os.path.exists(parent):
            self._makedirs(os.path.dirname(to))

        await self._move(at, to)

    async def movedir(self, at: str, to: str) -> None:
        from_fullpath = self._fullpath(at)
        if not os.path.isdir(from_fullpath):
            return

        await self._move(at, to)

    async def _move(self, at: str, to: str) -> None:
        source = self._fullpath(at)
        destination = self._fullpath(to)
        try:
            await asyncio.to_thread(shutil.move, source, destination)
        except FileNotFoundError as exc:
            raise File.NotFound() from exc
        except NotADirectoryError as exc:
            raise File.NotADirectory() from exc

    async def save(self, key: str, content: IFileContent) -> StorageFile:
        await content.seek(0)
        fullpath = self._fullpath(key)

        try:
            with open(fullpath, "wb") as buffer:
                await asyncio.to_thread(shutil.copyfileobj, content.file, buffer)
        except NotADirectoryError as exc:
            raise File.NotADirectory() from exc

        return self._from_path(fullpath)
