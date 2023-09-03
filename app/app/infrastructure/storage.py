from __future__ import annotations

import abc
import asyncio
from io import BytesIO
from typing import IO, TYPE_CHECKING, AsyncIterator, Iterator, Protocol, Self, cast

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath

__all__ = ["ContentReader", "IStorage", "StorageFile"]


_sentinel = object()


class ContentReader:
    __slots__ = ["content_iterator", "zipped"]

    def __init__(self, content_iterator: AsyncIterator[bytes], *, zipped: bool):
        self.content_iterator = content_iterator
        self.zipped = zipped

    @classmethod
    def from_iter(cls, it: Iterator[bytes], *, zipped: bool) -> Self:
        return cls(cls._iter_async(it), zipped=zipped)

    @staticmethod
    async def _iter_async(it: Iterator[bytes]) -> AsyncIterator[bytes]:
        loop = asyncio.get_running_loop()
        while True:
            value = await loop.run_in_executor(None, next, it, _sentinel)
            if value is _sentinel:
                break
            yield cast(bytes, value)

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self.content_iterator

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
            f"name={self.name!r}, "
            f"ns_path={self.ns_path!r}, "
            f"path={self.path!r}, "
            f"size={self.size!r}, "
            f"mtime={self.mtime!r}, "
            f"is_dir={self.is_dir()!r}"
            ")"
        )

    def __str__(self) -> str:
        return f"{self.ns_path}:{self.path}"

    def is_dir(self) -> bool:
        """True if file is a directory, False otherwise."""
        return self._is_dir


class IStorage(Protocol):
    location: str

    @abc.abstractmethod
    async def __aenter__(self) -> Self:
        raise NotImplementedError()

    @abc.abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        raise NotImplementedError()

    @abc.abstractmethod
    async def delete(self, ns_path: AnyPath, path: AnyPath) -> None:
        """
        Delete a file by path.

        If path does not exists or path is a directory, it will act as a no-op.

        Args:
            ns_path (AnyPath): Namespace path.
            path (AnyPath): File pathname relative to namespace.
        """

    @abc.abstractmethod
    async def deletedir(self, ns_path: AnyPath, path: AnyPath) -> None:
        """
        Delete a folder by path.

        If path does not exists, it will act as a no-op.

        Args:
            ns_path (AnyPath): Namespace path.
            path (AnyPath): Folder pathname relative to namespace.
        """

    @abc.abstractmethod
    async def emptydir(self, ns_path: AnyPath, path: AnyPath) -> None:
        """
        Deletes a folder content but not a folder itself.

        Args:
            ns_path (AnyPath): Namespace path.
            path (AnyPath): Folder pathname relative to namespace.
        """

    @abc.abstractmethod
    def download(self, ns_path: AnyPath, path: AnyPath) -> AsyncIterator[bytes]:
        """
        Return an iterator over a file content.

        Args:
            ns_path (AnyPath): Namespace path.
            path (AnyPath): File pathname relative to namespace.

        Raises:
            File.NotFound: If path not found or path is a directory.

        Yields:
            ContentReader: Iterator over a file content.
        """

    @abc.abstractmethod
    def downloaddir(self, ns_path: AnyPath, path: AnyPath) -> Iterator[bytes]:
        """
        Return an iterator over a zipped folder content.

        Args:
            ns_path (AnyPath): Namespace path.
            path (AnyPath): File pathname relative to namespace.

        Yields:
            ContentReader: Iterator over a file content.
        """

    @abc.abstractmethod
    async def exists(self, ns_path: AnyPath, path: AnyPath) -> bool:
        """
        Check whether if file exists or not in the specified path.

        Args:
            ns_path (AnyPath): Namespace path.
            path (AnyPath): File pathname relative to namespace.

        Returns:
            bool: True if file exists, False otherwise.
        """

    @abc.abstractmethod
    def iterdir(
        self,
        ns_path: AnyPath,
        path: AnyPath,
    ) -> AsyncIterator[StorageFile]:
        """
        Return an iterator of StorageFile objects for a given path.

        Args:
            ns_path (AnyPath): Namespace path.
            path (AnyPath): File pathname relative to namespace.

        Raises:
            File.NotFound: If given path does not exist
            File.NotADirectory: If given path is not a directory

        Yields:
            Iterator[StorageFile]: Iterator of StorageFile objects.
        """

    @abc.abstractmethod
    async def makedirs(self, ns_path: AnyPath, path: AnyPath) -> None:
        """
        Create a directory with any missing directories in a given path.

        Args:
            ns_path (AnyPath): Namespace path.
            path (AnyPath): File pathname relative to namespace.

        Raises:
            File.AlreadyExists: If some file already exists in a given path.
            File.NotADirectory: If some parent is not a directory.
        """

    @abc.abstractmethod
    async def move(
        self,
        at: tuple[AnyPath, AnyPath],
        to: tuple[AnyPath, AnyPath],
    ) -> None:
        """
        Move a file to the destination path. The destination path should include
        source file name. For example to move file 'f.txt' to a folder 'b', destination
        should as 'b/f.txt'.

        Args:
            at (tuple[AnyPath, AnyPath]): Namespace path and prefix to be replaced.
            to (tuple[AnyPath, AnyPath]): New mamespace path and prefix.

        Raises:
            File.NotFound: If source or destination path does not exist.
            File.NotADirectory: If some parent of the destination is not a directory.
        """

    @abc.abstractmethod
    async def movedir(
        self,
        at: tuple[AnyPath, AnyPath],
        to: tuple[AnyPath, AnyPath],
    ) -> None:
        """
        Move a folder to the destination path. The destination path should include
        source folder name. For example to move folder 'b' to a folder 'a', destination
        should as 'a/b'.

        If some parents in the destination path are missing, they will be created.
        If source path doesn't exists, it will act as a no-op.

        Args:
            at (tuple[AnyPath, AnyPath]): Namespace path and prefix to be replaced.
            to (tuple[AnyPath, AnyPath]): New mamespace path and prefix.

        Raises:
            File.NotADirectory: If some parent of the destination is not a directory.
        """

    @abc.abstractmethod
    async def save(
        self,
        ns_path: AnyPath,
        path: AnyPath,
        content: IO[bytes],
    ) -> StorageFile:
        """
        Save content to a given path.

        Args:
            ns_path (AnyPath): Namespace path.
            path (AnyPath): File pathname relative to namespace.
            content (IO[bytes]): Content to save.

        Raises:
            File.NotADirectory: If some parent is not a directory.

        Returns:
            StorageFile: Saved StorageFile.
        """
