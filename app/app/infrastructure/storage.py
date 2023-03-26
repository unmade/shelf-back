from __future__ import annotations

import abc
from io import BytesIO
from typing import IO, TYPE_CHECKING, AsyncIterator, Iterator, Protocol

if TYPE_CHECKING:
    from app.typedefs import StrOrPath

__all__ = ["ContentReader", "IStorage", "StorageFile"]


class ContentReader:
    __slots__ = ["content_iterator", "zipped"]

    def __init__(self, content_iterator: AsyncIterator[bytes], *, zipped):
        self.content_iterator = content_iterator
        self.zipped = zipped

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self.content_iterator

    async def __anext__(self) -> bytes:
        return await anext(self.content_iterator)

    async def stream(self) -> IO[bytes]:
        buffer = BytesIO()
        async for chunk in self:
            buffer.write(chunk)
        buffer.seek(0)
        return buffer


class StorageFile:
    __slots__ = ("name", "ns_path", "path", "size", "mtime", "_is_dir")

    def __init__(
        self,
        name: str,
        ns_path: str,
        path: str,
        size: int,
        mtime: float,
        is_dir: bool
    ):
        self.name = name
        self.ns_path = ns_path
        self.path = path
        self.size = size
        self.mtime = mtime
        self._is_dir = is_dir

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"name='{self.name}', "
            f"ns_path='{self.ns_path}', "
            f"path='{self.path}', "
            f"size={self.size}, "
            f"mtime={self.mtime}, "
            f"is_dir={self.is_dir()}"
            ")"
        )

    def __str__(self) -> str:
        return f"{self.ns_path}:{self.path}"

    def is_dir(self) -> bool:
        """True if file is a directory, False otherwise."""
        return self._is_dir


class IStorage(Protocol):
    location: str

    def __init__(self, location: StrOrPath):
        ...

    @abc.abstractmethod
    async def delete(self, ns_path: StrOrPath, path: StrOrPath) -> None:
        """
        Delete a file by path.

        If path does not exists or path is a directory, it will act as a no-op.

        Args:
            ns_path (StrOrPath): Namespace path.
            path (StrOrPath): File pathname relative to namespace.
        """

    @abc.abstractmethod
    async def deletedir(self, ns_path: StrOrPath, path: StrOrPath) -> None:
        """
        Delete a folder by path.

        If path does not exists, it will act as a no-op.

        Args:
            ns_path (StrOrPath): Namespace path.
            path (StrOrPath): Folder pathname relative to namespace.
        """

    @abc.abstractmethod
    async def emptydir(self, ns_path: StrOrPath, path: StrOrPath) -> None:
        """
        Deletes a folder content but not a folder itself.

        Args:
            ns_path (StrOrPath): Namespace path.
            path (StrOrPath): Folder pathname relative to namespace.
        """

    @abc.abstractmethod
    async def download(self, ns_path: StrOrPath, path: StrOrPath) -> ContentReader:
        """
        Return an iterator over a file content.

        Args:
            ns_path (StrOrPath): Namespace path.
            path (StrOrPath): File pathname relative to namespace.

        Raises:
            File.NotFound: If path not found or path is a directory.

        Yields:
            ContentReader: Iterator over a file content.
        """

    @abc.abstractmethod
    async def downloaddir(self, ns_path: StrOrPath, path: StrOrPath) -> ContentReader:
        """
        Return an iterator over a zipped folder content.

        Args:
            ns_path (StrOrPath): Namespace path.
            path (StrOrPath): File pathname relative to namespace.

        Yields:
            ContentReader: Iterator over a file content.
        """

    @abc.abstractmethod
    async def exists(self, ns_path: StrOrPath, path: StrOrPath) -> bool:
        """
        Check whether if file exists or not in the specified path.

        Args:
            ns_path (StrOrPath): Namespace path.
            path (StrOrPath): File pathname relative to namespace.

        Returns:
            bool: True if file exists, False otherwise.
        """

    @abc.abstractmethod
    async def get_modified_time(self, ns_path: StrOrPath, path: StrOrPath) -> float:
        """
        Get a datetime of the last modified time of the file.

        Args:
            ns_path (StrOrPath): Namespace path.
            path (StrOrPath): File pathname relative to namespace.

        Raises:
            File.NotFound: If file in path doesn't exists

        Returns:
            float: Last modified time of the file.
        """

    @abc.abstractmethod
    async def iterdir(
        self,
        ns_path: StrOrPath,
        path: StrOrPath,
    ) -> Iterator[StorageFile]:
        """
        Return an iterator of StorageFile objects for a given path.

        Args:
            ns_path (StrOrPath): Namespace path.
            path (StrOrPath): File pathname relative to namespace.

        Raises:
            File.NotFound: If given path does not exist
            File.NotADirectory: If given path is not a directory

        Yields:
            Iterator[StorageFile]: Iterator of StorageFile objects.
        """

    @abc.abstractmethod
    async def makedirs(self, ns_path: StrOrPath, path: StrOrPath) -> None:
        """
        Create a directory with any missing directories in a given path.

        Args:
            ns_path (StrOrPath): Namespace path.
            path (StrOrPath): File pathname relative to namespace.

        Raises:
            File.AlreadyExists: If some file already exists in a given path.
            File.NotADirectory: If some parent is not a directory.
        """

    @abc.abstractmethod
    async def move(
        self,
        ns_path: StrOrPath,
        from_path: StrOrPath,
        to_path: StrOrPath,
    ) -> None:
        """
        Move a file to the destination path. The destination path should include
        source file name. For example to move file 'f.txt' to a folder 'b', destination
        should as 'b/f.txt'.

        Args:
            ns_path (StrOrPath): Namespace path.
            from_path (StrOrPath): Current file pathname relative to namespace.
            to_path (StrOrPath): Next file pathname relative to namespace.

        Raises:
            File.NotFound: If source or destination path does not exist.
            File.NotADirectory: If some parent of the destination is not a directory.
        """

    @abc.abstractmethod
    async def movedir(
        self,
        ns_path: StrOrPath,
        from_path: StrOrPath,
        to_path: StrOrPath,
    ) -> None:
        """
        Move a folder to the destination path. The destination path should include
        source folder name. For example to move folder 'b' to a folder 'a', destination
        should as 'a/b'.

        If some parents in the destination path are missing, they will be created.
        If source path doesn't exists, it will act as a no-op.

        Args:
            ns_path (StrOrPath): Namespace path.
            from_path (StrOrPath): Current folder pathname relative to namespace.
            to_path (StrOrPath): Next folder pathname relative to namespace.

        Raises:
            File.NotADirectory: If some parent of the destination is not a directory.
        """

    @abc.abstractmethod
    async def save(
        self,
        ns_path: StrOrPath,
        path: StrOrPath,
        content: IO[bytes],
    ) -> StorageFile:
        """
        Save content to a given path.

        Args:
            ns_path (StrOrPath): Namespace path.
            path (StrOrPath): File pathname relative to namespace.
            content (IO[bytes]): Content to save.

        Raises:
            File.NotADirectory: If some parent is not a directory.

        Returns:
            StorageFile: Saved StorageFile.
        """

    @abc.abstractmethod
    async def size(self, ns_path: StrOrPath, path: StrOrPath) -> int:
        """
        Get the total size, in bytes, of the file referenced by path.

        Args:
            ns_path (StrOrPath): Namespace path.
            path (StrOrPath): File pathname relative to namespace.

        Raises:
            File.NotFound: If given path does not exist.

        Returns:
            int: Total size in bytes.
        """

    @abc.abstractmethod
    async def thumbnail(self, ns_path: StrOrPath, path: StrOrPath, size: int) -> bytes:
        """
        Generate thumbnail with a specified size for the given path.

        Args:
            ns_path (StrOrPath): Namespace path.
            path (StrOrPath): File pathname relative to namespace.
            size (int): Size of thumbnail in pixels.

        Raises:
            File.NotFound: If given path does not exist.
            File.IsADirectory: If given path is a directory.
            errors.ThumbnailUnavailable: If image type is not supported or file
                is not an image.

        Returns:
            bytes: Thumbnail content.
        """
