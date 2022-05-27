from __future__ import annotations

import glob
import os
import os.path
import shutil
from io import BytesIO
from typing import IO, TYPE_CHECKING, Iterator

import zipfly
from asgiref.sync import sync_to_async
from PIL import Image, UnidentifiedImageError
from PIL.ImageOps import exif_transpose

from app import errors

from .base import Storage, StorageFile

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
        try:
            if os.path.isdir(fullpath):
                shutil.rmtree(fullpath)
            else:
                os.unlink(fullpath)
        except FileNotFoundError as exc:
            raise errors.FileNotFound() from exc

    def download(self, ns_path: StrOrPath, path: StrOrPath) -> Iterator[bytes]:
        fullpath = self._joinpath(self.location, ns_path, path)
        pathnames = glob.iglob(self._joinpath(fullpath, "**/*"), recursive=True)
        if os.path.isdir(fullpath):
            paths = [
                {
                    "fs": pathname,
                    "n": os.path.relpath(pathname, fullpath),
                }
                for pathname in pathnames
                if os.path.isfile(pathname)
            ]
            return zipfly.ZipFly(paths=paths).generator()  # type: ignore

        return self._readchunks(fullpath)

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
    def thumbnail(
        self,
        ns_path: StrOrPath,
        path: StrOrPath,
        size: int,
    ) -> tuple[int, IO[bytes]]:
        fullpath = self._joinpath(self.location, ns_path, path)
        buffer = BytesIO()
        try:
            with Image.open(fullpath) as im:
                im.thumbnail((size, size))
                exif_transpose(im).save(buffer, im.format)
        except FileNotFoundError as exc:
            raise errors.FileNotFound() from exc
        except IsADirectoryError as exc:
            raise errors.IsADirectory(f"Path '{path}' is a directory") from exc
        except UnidentifiedImageError as exc:
            msg = f"Can't generate thumbnail for a file: '{path}'"
            raise errors.ThumbnailUnavailable(msg) from exc

        size = buffer.seek(0, 2)
        buffer.seek(0)

        return size, buffer
