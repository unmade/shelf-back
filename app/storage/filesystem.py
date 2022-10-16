from __future__ import annotations

import datetime
import glob
import os
import os.path
import shutil
from io import BytesIO
from typing import IO, TYPE_CHECKING, Iterator, cast

import stream_zip
from asgiref.sync import sync_to_async
from PIL import Image, UnidentifiedImageError
from PIL.ImageOps import exif_transpose

from app import errors

from .base import Storage, StorageFile, StreamZipFile

if TYPE_CHECKING:
    from app.typedefs import StrOrPath


class FileSystemStorage(Storage):
    @staticmethod
    def _joinpath(path: StrOrPath, *paths: StrOrPath) -> str:
        """Join two or more paths and return a normalize path."""
        return os.path.normpath(os.path.join(path, *paths))

    @staticmethod
    def _readchunks(path: StrOrPath) -> Iterator[bytes]:
        chunk_size = 4096
        with open(path, 'rb') as f:
            has_content = True
            while has_content:
                chunk = f.read(chunk_size)
                has_content = len(chunk) == chunk_size
                yield chunk

    def _from_entry(self, ns_path: StrOrPath, entry: os.DirEntry[str]) -> StorageFile:
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

    def _from_path(self, ns_path: StrOrPath, path: str) -> StorageFile:
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
    def delete(self, ns_path: StrOrPath, path: StrOrPath) -> None:
        fullpath = self._joinpath(self.location, ns_path, path)
        if not os.path.isdir(fullpath):
            try:
                os.unlink(fullpath)
            except FileNotFoundError:
                pass

    @sync_to_async
    def deletedir(self, ns_path: StrOrPath, path: StrOrPath) -> None:
        fullpath = self._joinpath(self.location, ns_path, path)
        try:
            shutil.rmtree(fullpath)
        except (FileNotFoundError, NotADirectoryError):
            pass

    def download(self, ns_path: StrOrPath, path: StrOrPath) -> Iterator[bytes]:
        fullpath = self._joinpath(self.location, ns_path, path)
        file = self._from_path(ns_path, fullpath)
        if file.is_dir():
            raise errors.FileNotFound()
        return self._readchunks(fullpath)

    def downloaddir(self, ns_path: StrOrPath, path: StrOrPath) -> Iterator[bytes]:
        return cast(
            Iterator[bytes],
            stream_zip.stream_zip(self._downloaddir_iter(ns_path, path))
        )

    def _downloaddir_iter(
        self,
        ns_path: StrOrPath,
        path: StrOrPath,
    ) -> Iterator[StreamZipFile]:
        fullpath = self._joinpath(self.location, ns_path, path)
        pathnames = glob.iglob(self._joinpath(fullpath, "**/*"), recursive=True)
        for pathname in pathnames:
            file = self._from_path(ns_path, pathname)
            if file.is_dir():
                continue
            with open(pathname, "rb") as content:
                yield StreamZipFile(
                    path=os.path.relpath(file.path, path),
                    modified_at=datetime.datetime.fromtimestamp(file.mtime),
                    perms=0o600,
                    compression=stream_zip.ZIP_32,
                    content=content,
                )

    @sync_to_async
    def exists(self, ns_path: StrOrPath, path: StrOrPath) -> bool:
        fullpath = self._joinpath(self.location, ns_path, path)
        return os.path.exists(fullpath)

    @sync_to_async
    def get_modified_time(self, ns_path: StrOrPath, path: StrOrPath) -> float:
        fullpath = self._joinpath(self.location, ns_path, path)
        try:
            return os.lstat(fullpath).st_mtime
        except FileNotFoundError as exc:
            raise errors.FileNotFound() from exc

    @sync_to_async
    def iterdir(self, ns_path: StrOrPath, path: StrOrPath) -> Iterator[StorageFile]:
        dir_path = self._joinpath(self.location, ns_path, path)
        try:
            entries = os.scandir(dir_path)
        except FileNotFoundError as exc:
            raise errors.FileNotFound() from exc
        except NotADirectoryError as exc:
            raise errors.NotADirectory() from exc

        for entry in entries:
            try:
                yield self._from_entry(ns_path, entry)
            except FileNotFoundError:
                if entry.is_symlink():
                    continue
                raise  # pragma: no cover

    @sync_to_async
    def makedirs(self, ns_path: StrOrPath, path: StrOrPath) -> None:
        self._makedirs(ns_path, path)

    def _makedirs(self, ns_path: StrOrPath, path: StrOrPath) -> None:
        fullpath = self._joinpath(self.location, ns_path, path)
        try:
            os.makedirs(fullpath, exist_ok=True)
        except FileExistsError as exc:
            raise errors.FileAlreadyExists() from exc
        except NotADirectoryError as exc:
            raise errors.NotADirectory() from exc

    @sync_to_async
    def move(
        self,
        ns_path: StrOrPath,
        from_path: StrOrPath,
        to_path: StrOrPath,
    ) -> None:
        from_fullpath = self._joinpath(self.location, ns_path, from_path)
        to_fullpath = self._joinpath(self.location, ns_path, to_path)
        if os.path.isdir(from_fullpath):
            raise errors.FileNotFound() from None

        parent = os.path.dirname(to_fullpath)
        if not os.path.exists(parent):
            self._makedirs(ns_path, os.path.dirname(to_path))

        self._move(ns_path, from_path, to_path)

    @sync_to_async
    def movedir(
        self,
        ns_path: StrOrPath,
        from_path: StrOrPath,
        to_path: StrOrPath,
    ) -> None:
        from_fullpath = self._joinpath(self.location, ns_path, from_path)
        if not os.path.isdir(from_fullpath):
            return

        self._move(ns_path, from_path, to_path)

    def _move(
        self,
        ns_path: StrOrPath,
        from_path: StrOrPath,
        to_path: StrOrPath,
    ) -> None:
        source = self._joinpath(self.location, ns_path, from_path)
        destination = self._joinpath(self.location, ns_path, to_path)
        try:
            shutil.move(source, destination)
        except FileNotFoundError as exc:
            raise errors.FileNotFound() from exc
        except NotADirectoryError as exc:
            raise errors.NotADirectory() from exc

    @sync_to_async
    def save(
        self,
        ns_path: StrOrPath,
        path: StrOrPath,
        content: IO[bytes],
    ) -> StorageFile:
        content.seek(0)
        fullpath = self._joinpath(self.location, ns_path, path)

        try:
            with open(fullpath, "wb") as buffer:
                shutil.copyfileobj(content, buffer)
        except NotADirectoryError as exc:
            raise errors.NotADirectory() from exc

        return self._from_path(ns_path, fullpath)

    @sync_to_async
    def size(self, ns_path: StrOrPath, path: StrOrPath) -> int:
        fullpath = self._joinpath(self.location, ns_path, path)
        try:
            return os.lstat(fullpath).st_size
        except FileNotFoundError as exc:
            raise errors.FileNotFound() from exc

    @sync_to_async
    def thumbnail(self, ns_path: StrOrPath, path: StrOrPath, size: int) -> bytes:
        fullpath = self._joinpath(self.location, ns_path, path)
        buffer = BytesIO()
        try:
            with Image.open(fullpath) as im:
                im.thumbnail((size, size))
                exif_transpose(im).save(buffer, im.format, compress_level=4)
        except FileNotFoundError as exc:
            raise errors.FileNotFound() from exc
        except IsADirectoryError as exc:
            raise errors.IsADirectory(f"Path '{path}' is a directory") from exc
        except UnidentifiedImageError as exc:
            msg = f"Can't generate thumbnail for a file: '{path}'"
            raise errors.ThumbnailUnavailable(msg) from exc

        buffer.seek(0)
        return buffer.read()
