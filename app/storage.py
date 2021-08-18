from __future__ import annotations

import abc
import glob
import os
import os.path
import shutil
from io import BytesIO
from typing import IO, TYPE_CHECKING, Iterator

import zipfly
from asgiref.sync import sync_to_async
from PIL import Image, UnidentifiedImageError

from app import config, errors

if TYPE_CHECKING:
    from app.typedefs import StrOrPath


def joinpath(path: StrOrPath, *paths: StrOrPath) -> str:
    """Join two or more paths and return a normalize path."""
    return os.path.normpath(os.path.join(path, *paths))


class StorageFile:
    __slots__ = ("name", "path", "size", "mtime", "_is_dir")

    def __init__(self, name: str, path: str, size: int, mtime: float, is_dir: bool):
        self.name = name
        self.path = path
        self.size = size
        self.mtime = mtime
        self._is_dir = is_dir

    def __str__(self) -> str:
        return str(self.path)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"name='{self.name}', "
            f"path='{self.path}', "
            f"size={self.size}, "
            f"mtime={self.mtime}, "
            f"is_dir={self.is_dir()}"
            ")"
        )

    def is_dir(self) -> bool:
        """True if file is a directory, False otherwise."""
        return self._is_dir


class Storage:
    def __init__(self, location: StrOrPath):
        self.location = str(location)

    @abc.abstractmethod
    async def delete(self, path: StrOrPath) -> None:
        """
        Delete file or a folder by path.

        Args:
            path (StrOrPath): Path relative to storage location.

        Raises:
            errors.FileNotFound: If file not found.
        """

    @abc.abstractmethod
    def download(self, path: StrOrPath) -> Iterator[bytes]:
        """
        Return an iterator over a file content. If a file is a folder, then it will be
        be a zip archive.

        Args:
            path (StrOrPath): Path relative to storage location.

        Yields:
            Iterator[bytes]: Iterator to a file content.
        """

    @abc.abstractmethod
    async def exists(self, path: StrOrPath) -> bool:
        """
        Check whether if file exists or not in the specified path.

        Args:
            path (StrOrPath): Path relative to storage location.

        Returns:
            bool: True if file exists, False otherwise.
        """

    @abc.abstractmethod
    async def get_modified_time(self, path: StrOrPath) -> float:
        """
        Get a datetime of the last modified time of the file.

        Args:
            path (StrOrPath): Path relative to storage location.

        Raises:
            errors.FileNotFound: If file in path doesn't exists

        Returns:
            float: Last modified time of the file.
        """

    @abc.abstractmethod
    async def iterdir(self, path: StrOrPath) -> Iterator[StorageFile]:
        """
        Return an iterator of StorageFile objects for a given path.

        Args:
            path (StrOrPath): Path relative to storage location.

        Raises:
            errors.FileNotFound: If given path does not exist
            errors.NotADirectory: If given path is not a directory

        Yields:
            Iterator[StorageFile]: Iterator of StorageFile objects.
        """

    @abc.abstractmethod
    async def makedirs(self, path: StrOrPath) -> None:
        """
        Create a directory with any missing directories in a given path.

        Args:
            path (StrOrPath): Path relative to a storage location.

        Raises:
            errors.FileAlreadyExists: If some file already exists in a given path.
            errors.NotADirectory: If some parent is not a directory.
        """

    @abc.abstractmethod
    async def move(self, from_path: StrOrPath, to_path: StrOrPath) -> None:
        """
        Move file or folder to a destination path. Destination path should include
        source file name. For example to move file 'f.txt' to a folder 'b', destination
        should as 'b/f.txt'.

        Args:
            from_path (StrOrPath): Current file path relative to storage location.
            to_path (StrOrPath): New file path relative to storage location.

        Raises:
            errors.FileNotFound: If source or destination path does not exist.
            errors.NotADirectory: If some parent of the destination is not a directory.
        """

    @abc.abstractmethod
    async def save(self, path: StrOrPath, content: IO[bytes]) -> StorageFile:
        """
        Save content to a given path.

        Args:
            path (StrOrPath): Path relative to storage location.
            content (IO[bytes]): Content to save.

        Raises:
            errors.NotADirectory: If some parent is not a directory.

        Returns:
            StorageFile: Saved StorageFile.
        """

    @abc.abstractmethod
    async def size(self, path: StrOrPath) -> int:
        """
        Get the total size, in bytes, of the file referenced by path.

        Args:
            path (StrOrPath): Path relative to storage location.

        Raises:
            errors.FileNotFound: If given path does not exist.

        Returns:
            int: Total size in bytes.
        """

    @abc.abstractmethod
    async def thumbnail(self, path: StrOrPath, size: int) -> tuple[int, IO[bytes]]:
        """
        Generate thumbnail with a specified size for the given path.

        Args:
            path (StrOrPath): Path relative to storage location.
            size (int): Size of thumbnail in pixels.

        Raises:
            errors.FileNotFound: If given path does not exist.
            errors.IsADirectory: If given path is a directory.
            errors.ThumbnailUnavailable: If image type is not supported or file
                is not an image.

        Returns:
            tuple[int, IO[bytes]]: Size, in bytes and a thumbnail.
        """


class LocalStorage(Storage):
    def _from_path(self, path: StrOrPath) -> StorageFile:
        stat = os.lstat(path)
        return StorageFile(
            name=os.path.basename(path),
            path=os.path.relpath(path, self.location),
            size=stat.st_size,
            mtime=stat.st_mtime,
            is_dir=os.path.isdir(path),
        )

    def _from_entry(self, entry: os.DirEntry[str]) -> StorageFile:
        stat = entry.stat()
        return StorageFile(
            name=entry.name,
            path=os.path.relpath(entry.path, self.location),
            size=stat.st_size,
            mtime=stat.st_mtime,
            is_dir=entry.is_dir(),
        )

    @staticmethod
    def _readchunks(path: StrOrPath) -> Iterator[bytes]:
        chunk_size = 4096
        with open(path, 'rb') as f:
            has_content = True
            while has_content:
                chunk = f.read(chunk_size)
                has_content = len(chunk) == chunk_size
                yield chunk

    @sync_to_async
    def delete(self, path: StrOrPath) -> None:
        fullpath = joinpath(self.location, path)
        try:
            if os.path.isdir(fullpath):
                shutil.rmtree(fullpath)
            else:
                os.unlink(fullpath)
        except FileNotFoundError as exc:
            raise errors.FileNotFound() from exc

    def download(self, path: StrOrPath) -> Iterator[bytes]:
        fullpath = joinpath(self.location, path)
        pathnames = glob.iglob(joinpath(fullpath, "**/*"), recursive=True)
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
    def exists(self, path: StrOrPath) -> bool:
        fullpath = joinpath(self.location, path)
        return os.path.exists(fullpath)

    @sync_to_async
    def get_modified_time(self, path: StrOrPath) -> float:
        fullpath = joinpath(self.location, path)
        try:
            return os.lstat(fullpath).st_mtime
        except FileNotFoundError as exc:
            raise errors.FileNotFound() from exc

    @sync_to_async
    def iterdir(self, path: StrOrPath) -> Iterator[StorageFile]:
        dir_path = joinpath(self.location, path)
        try:
            return (self._from_entry(entry) for entry in os.scandir(dir_path))
        except FileNotFoundError as exc:
            raise errors.FileNotFound() from exc
        except NotADirectoryError as exc:
            raise errors.NotADirectory() from exc

    @sync_to_async
    def makedirs(self, path: StrOrPath) -> None:
        fullpath = joinpath(self.location, path)
        try:
            os.makedirs(fullpath, exist_ok=True)
        except FileExistsError as exc:
            raise errors.FileAlreadyExists() from exc
        except NotADirectoryError as exc:
            raise errors.NotADirectory() from exc

    @sync_to_async
    def move(self, from_path: StrOrPath, to_path: StrOrPath) -> None:
        source = joinpath(self.location, from_path)
        destination = joinpath(self.location, to_path)
        try:
            shutil.move(source, destination)
        except FileNotFoundError as exc:
            raise errors.FileNotFound() from exc
        except NotADirectoryError as exc:
            raise errors.NotADirectory() from exc

    @sync_to_async
    def save(self, path: StrOrPath, content: IO[bytes]) -> StorageFile:
        content.seek(0)
        fullpath = joinpath(self.location, path)

        try:
            with open(fullpath, "wb") as buffer:
                shutil.copyfileobj(content, buffer)
        except NotADirectoryError as exc:
            raise errors.NotADirectory() from exc

        return self._from_path(fullpath)

    @sync_to_async
    def size(self, path: StrOrPath) -> int:
        fullpath = joinpath(self.location, path)
        try:
            return os.lstat(fullpath).st_size
        except FileNotFoundError as exc:
            raise errors.FileNotFound() from exc

    @sync_to_async
    def thumbnail(self, path: StrOrPath, size: int) -> tuple[int, IO[bytes]]:
        fullpath = joinpath(self.location, path)
        buffer = BytesIO()
        try:
            with Image.open(fullpath) as im:
                im.thumbnail((size, size))
                im.save(buffer, im.format)
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


storage: Storage = LocalStorage(config.STORAGE_LOCATION)
