from __future__ import annotations

import contextlib
import datetime
import glob
import os
import os.path
import shutil
from typing import IO, TYPE_CHECKING, AsyncIterator, Iterator, Self

import stream_zip
from asgiref.sync import sync_to_async

from app.app.files.domain import File
from app.app.infrastructure.storage import IStorage, StorageFile
from app.config import FileSystemStorageConfig

from ._datastructures import StreamZipFile

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath

__all__ = ["FileSystemStorage"]


class FileSystemStorage(IStorage):
    def __init__(self, config: FileSystemStorageConfig):
        self.location = config.fs_location

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

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

    @sync_to_async
    def delete(self, ns_path: AnyPath, path: AnyPath) -> None:
        fullpath = self._joinpath(self.location, ns_path, path)
        if not os.path.isdir(fullpath):
            with contextlib.suppress(FileNotFoundError):
                os.unlink(fullpath)

    @sync_to_async
    def deletedir(self, ns_path: AnyPath, path: AnyPath) -> None:
        fullpath = self._joinpath(self.location, ns_path, path)
        with contextlib.suppress(FileNotFoundError, NotADirectoryError):
            shutil.rmtree(fullpath)

    @sync_to_async
    def emptydir(self, ns_path: AnyPath, path: AnyPath) -> None:
        fullpath = self._joinpath(self.location, ns_path, path)
        with contextlib.suppress(FileNotFoundError, NotADirectoryError):
            for entry in os.scandir(fullpath):
                if entry.is_dir():
                    shutil.rmtree(entry.path)
                else:
                    os.unlink(entry.path)

    async def download(self, ns_path: AnyPath, path) -> AsyncIterator[bytes]:
        fullpath = self._joinpath(self.location, ns_path, path)
        try:
            file = self._from_path(ns_path, fullpath)
        except FileNotFoundError as exc:
            raise File.NotFound() from exc

        if file.is_dir():
            raise File.NotFound()

        with open(str(fullpath), "rb", buffering=4096) as f:
            for chunk in f:
                yield chunk

    def downloaddir(self, ns_path: AnyPath, path: AnyPath) -> Iterator[bytes]:
        return stream_zip.stream_zip(  # type: ignore[no-any-return]
            self._downloaddir_iter(ns_path, path)
        )

    def _downloaddir_iter(
        self,
        ns_path: AnyPath,
        path: AnyPath,
    ) -> Iterator[StreamZipFile]:
        fullpath = self._joinpath(self.location, ns_path, path)
        pathnames = glob.iglob(self._joinpath(fullpath, "**/*"), recursive=True)
        for pathname in pathnames:
            file = self._from_path(ns_path, pathname)
            if file.is_dir():
                continue
            with open(pathname, "rb") as content:
                yield StreamZipFile(
                    path=os.path.relpath(str(file.path), str(path)),
                    modified_at=datetime.datetime.fromtimestamp(file.mtime),
                    perms=0o600,
                    compression=stream_zip.ZIP_32,
                    content=content,
                )

    @sync_to_async
    def exists(self, ns_path: AnyPath, path: AnyPath) -> bool:
        fullpath = self._joinpath(self.location, ns_path, path)
        return os.path.exists(fullpath)

    async def iterdir(
        self, ns_path: AnyPath, path: AnyPath
    ) -> AsyncIterator[StorageFile]:
        dir_path = self._joinpath(self.location, ns_path, path)
        try:
            entries = os.scandir(dir_path)
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

    @sync_to_async
    def makedirs(self, ns_path: AnyPath, path: AnyPath) -> None:
        self._makedirs(ns_path, path)

    def _makedirs(self, ns_path: AnyPath, path: AnyPath) -> None:
        fullpath = self._joinpath(self.location, ns_path, path)
        try:
            os.makedirs(fullpath, exist_ok=True)
        except FileExistsError as exc:
            raise File.AlreadyExists() from exc
        except NotADirectoryError as exc:
            raise File.NotADirectory() from exc

    @sync_to_async
    def move(
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

        self._move(at, to)

    @sync_to_async
    def movedir(
        self,
        at: tuple[AnyPath, AnyPath],
        to: tuple[AnyPath, AnyPath],
    ) -> None:
        from_fullpath = self._joinpath(self.location, *at)
        if not os.path.isdir(from_fullpath):
            return

        self._move(at, to)

    def _move(
        self,
        at: tuple[AnyPath, AnyPath],
        to: tuple[AnyPath, AnyPath],
    ) -> None:
        source = self._joinpath(self.location, *at)
        destination = self._joinpath(self.location, *to)
        try:
            shutil.move(source, destination)
        except FileNotFoundError as exc:
            raise File.NotFound() from exc
        except NotADirectoryError as exc:
            raise File.NotADirectory() from exc

    @sync_to_async
    def save(
        self,
        ns_path: AnyPath,
        path: AnyPath,
        content: IO[bytes],
    ) -> StorageFile:
        content.seek(0)
        fullpath = self._joinpath(self.location, ns_path, path)

        try:
            with open(fullpath, "wb") as buffer:
                shutil.copyfileobj(content, buffer)
        except NotADirectoryError as exc:
            raise File.NotADirectory() from exc

        return self._from_path(ns_path, fullpath)
