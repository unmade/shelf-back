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

    from app.app.files.domain import AnyPath, IFileContent

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
    def _has_path(target: str, paths: Collection[AnyPath] | None) -> bool:
        if paths is None:
            return True

        target = target.lower()
        haystack = {str(p).lower() for p in paths}
        if target in haystack:
            return True

        return any(target.startswith(prefix) for prefix in haystack)

    @staticmethod
    def _joinpath(path: AnyPath, *paths: AnyPath) -> str:
        """Join two or more paths and return a normalize path."""
        return os.path.normpath(os.path.join(str(path), *(str(p) for p in paths)))

    def _from_entry(self, ns_path: AnyPath, entry: os.DirEntry[str]) -> StorageFile:
        ns_path = str(ns_path)
        stat = entry.stat()
        return StorageFile(
            name=entry.name,
            ns_path=ns_path,
            path=entry.path[len(self.location) + len(ns_path) + 2:],
            size=stat.st_size,
            mtime=stat.st_mtime,
            is_dir=entry.is_dir(),
        )

    def _from_path(self, ns_path: AnyPath, path: str) -> StorageFile:
        ns_path = str(ns_path)
        stat = os.lstat(path)
        return StorageFile(
            name=os.path.basename(path),
            ns_path=ns_path,
            path=path[len(self.location) + len(ns_path) + 2:],
            size=stat.st_size,
            mtime=stat.st_mtime,
            is_dir=os.path.isdir(path),
        )

    async def delete(self, ns_path: AnyPath, path: AnyPath) -> None:
        fullpath = self._joinpath(self.location, ns_path, path)
        if not os.path.isdir(fullpath):
            with contextlib.suppress(FileNotFoundError):
                await asyncio.to_thread(os.unlink, fullpath)

    async def delete_batch(self, items: Iterable[tuple[AnyPath, AnyPath]]) -> None:
        for ns_path, path in items:
            await self.delete(ns_path, path)

    async def deletedir(self, ns_path: AnyPath, path: AnyPath) -> None:
        fullpath = self._joinpath(self.location, ns_path, path)
        with contextlib.suppress(FileNotFoundError, NotADirectoryError):
            await asyncio.to_thread(shutil.rmtree, fullpath)

    async def emptydir(self, ns_path: AnyPath, path: AnyPath) -> None:
        fullpath = self._joinpath(self.location, ns_path, path)
        async with asyncio.TaskGroup() as tg:
            with contextlib.suppress(FileNotFoundError, NotADirectoryError):
                for entry in await asyncio.to_thread(os.scandir, fullpath):
                    if entry.is_dir():
                        tg.create_task(asyncio.to_thread(shutil.rmtree, entry.path))
                    else:
                        tg.create_task(asyncio.to_thread(os.unlink, entry.path))

    async def download(self, ns_path: AnyPath, path) -> AsyncIterator[bytes]:
        fullpath = self._joinpath(self.location, ns_path, path)

        try:
            file = self._from_path(ns_path, fullpath)
        except FileNotFoundError as exc:
            raise File.NotFound() from exc

        if file.is_dir():
            raise File.NotFound()

        with open(fullpath, "rb", buffering=4096) as f:
            for chunk in f:
                yield chunk

    def downloaddir(
        self,
        ns_path: AnyPath,
        path: AnyPath,
        include_paths: Collection[AnyPath] | None = None,
    ) -> Iterator[bytes]:
        return stream_zip.stream_zip(  # type: ignore[no-any-return]
            self._downloaddir_iter(ns_path, path, include_paths)
        )

    def _downloaddir_iter(
        self,
        ns_path: AnyPath,
        path: AnyPath,
        include_paths: Collection[AnyPath] | None = None,
    ) -> Iterator[StreamZipFile]:
        fullpath = self._joinpath(self.location, ns_path, path)
        pathnames = glob.iglob(self._joinpath(fullpath, "**/*"), recursive=True)
        for pathname in pathnames:
            file = self._from_path(ns_path, pathname)
            if file.is_dir():
                continue

            if not self._has_path(str(file.path), include_paths):
                continue

            with open(pathname, "rb") as content:
                yield StreamZipFile(
                    path=os.path.relpath(str(file.path), str(path)),
                    modified_at=datetime.datetime.fromtimestamp(file.mtime),
                    perms=0o600,
                    compression=stream_zip.ZIP_32,
                    content=content,
                )

    async def exists(self, ns_path: AnyPath, path: AnyPath) -> bool:
        fullpath = self._joinpath(self.location, ns_path, path)
        return os.path.exists(fullpath)

    async def iterdir(
        self, ns_path: AnyPath, path: AnyPath
    ) -> AsyncIterator[StorageFile]:
        dir_path = self._joinpath(self.location, ns_path, path)
        try:
            entries = await asyncio.to_thread(os.scandir, dir_path)
        except FileNotFoundError as exc:
            raise File.NotFound() from exc
        except NotADirectoryError as exc:
            raise File.NotADirectory() from exc

        for entry in entries:
            try:
                yield self._from_entry(ns_path, entry)
            except FileNotFoundError:
                if entry.is_symlink():
                    continue
                raise  # pragma: no cover

    async def makedirs(self, ns_path: AnyPath, path: AnyPath) -> None:
        self._makedirs(ns_path, path)

    def _makedirs(self, ns_path: AnyPath, path: AnyPath) -> None:
        fullpath = self._joinpath(self.location, ns_path, path)
        try:
            os.makedirs(fullpath, exist_ok=True)
        except FileExistsError as exc:
            raise File.AlreadyExists() from exc
        except NotADirectoryError as exc:
            raise File.NotADirectory() from exc

    async def move(
        self,
        at: tuple[AnyPath, AnyPath],
        to: tuple[AnyPath, AnyPath],
    ) -> None:
        from_fullpath = self._joinpath(self.location, *at)
        to_fullpath = self._joinpath(self.location, *to)
        if os.path.isdir(from_fullpath):
            raise File.NotFound() from None

        parent = os.path.dirname(to_fullpath)
        if not os.path.exists(parent):
            to_ns_path, to_path = to
            self._makedirs(to_ns_path, os.path.dirname(str(to_path)))

        await self._move(at, to)

    async def movedir(
        self,
        at: tuple[AnyPath, AnyPath],
        to: tuple[AnyPath, AnyPath],
    ) -> None:
        from_fullpath = self._joinpath(self.location, *at)
        if not os.path.isdir(from_fullpath):
            return

        await self._move(at, to)

    async def _move(
        self,
        at: tuple[AnyPath, AnyPath],
        to: tuple[AnyPath, AnyPath],
    ) -> None:
        source = self._joinpath(self.location, *at)
        destination = self._joinpath(self.location, *to)
        try:
            await asyncio.to_thread(shutil.move, source, destination)
        except FileNotFoundError as exc:
            raise File.NotFound() from exc
        except NotADirectoryError as exc:
            raise File.NotADirectory() from exc

    async def save(
        self,
        ns_path: AnyPath,
        path: AnyPath,
        content: IFileContent,
    ) -> StorageFile:
        await content.seek(0)
        fullpath = self._joinpath(self.location, ns_path, path)

        try:
            with open(fullpath, "wb") as buffer:
                await asyncio.to_thread(shutil.copyfileobj, content.file, buffer)
        except NotADirectoryError as exc:
            raise File.NotADirectory() from exc

        return self._from_path(ns_path, fullpath)
