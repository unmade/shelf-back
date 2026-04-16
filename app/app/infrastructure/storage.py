from __future__ import annotations

import abc
from typing import TYPE_CHECKING, NamedTuple, Protocol, Self

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Collection, Iterable

    from app.app.blobs.domain import IBlobContent

__all__ = ["IStorage", "StorageFile"]


class DownloadBatchItem(NamedTuple):
    key: str
    is_dir: bool


class StorageFile:
    __slots__ = ("name", "path", "size", "mtime", "_is_dir")

    def __init__(
        self,
        name: str,
        path: str,
        size: int,
        mtime: float,
        is_dir: bool
    ):
        self.name = name
        self.path = path
        self.size = size
        self.mtime = mtime
        self._is_dir = is_dir

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"name={self.name!r}, "
            f"path={self.path!r}, "
            f"size={self.size!r}, "
            f"mtime={self.mtime!r}, "
            f"is_dir={self.is_dir()!r}"
            ")"
        )

    def __str__(self) -> str:
        return self.path

    def is_dir(self) -> bool:
        """True if file is a directory, False otherwise."""
        return self._is_dir


class IStorage(Protocol):
    location: str

    @abc.abstractmethod
    async def __aenter__(self) -> Self:
        raise NotImplementedError()  # pragma: no cover

    @abc.abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        raise NotImplementedError()  # pragma: no cover

    @abc.abstractmethod
    async def delete(self, key: str) -> None:
        """
        Delete a file by key.

        If key does not exists or key is a directory, it will act as a no-op.
        """

    @abc.abstractmethod
    async def delete_batch(self, keys: Iterable[str]) -> None:
        """
        Delete multiple files by provided keys.

        If key does not exists or key is a directory, it will act as a no-op.
        """

    @abc.abstractmethod
    async def deletedir(self, key: str) -> None:
        """
        Delete a folder by key.

        If key does not exists, it will act as a no-op.
        """

    @abc.abstractmethod
    async def emptydir(self, key: str) -> None:
        """
        Deletes a folder content but not a folder itself.
        """

    @abc.abstractmethod
    def download(self, key: str) -> AsyncIterator[bytes]:
        """
        Return an iterator over a file content.

        Raises:
            File.NotFound: If key not found or key is a directory.
        """

    @abc.abstractmethod
    def download_batch(self, items: Iterable[DownloadBatchItem]) -> Iterable[bytes]:
        """Return an iterable over a zipped files at given keys."""

    @abc.abstractmethod
    def downloaddir(
        self,
        key: str,
        include_keys: Collection[str] | None = None,
    ) -> Iterable[bytes]:
        """
        Return an iterable over a zipped folder content.

        If optional `include_keys` is provided, then only those keys in the folder
        will be included.
        """

    @abc.abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Check whether a file exists or not at the specified key.
        """

    @abc.abstractmethod
    def iterdir(self, key: str) -> AsyncIterator[StorageFile]:
        """
        Return an iterator of StorageFile objects for a given key.

        Raises:
            File.NotFound: If given key does not exist
            File.NotADirectory: If given key is not a directory
        """

    @abc.abstractmethod
    async def makedirs(self, key: str) -> None:
        """
        Create a directory with any missing directories in a given key.

        Raises:
            File.AlreadyExists: If some file already exists at a given key.
            File.NotADirectory: If some parent is not a directory.
        """

    @abc.abstractmethod
    async def move(self, at: str, to: str) -> None:
        """
        Move a file to the destination key. The destination key should include
        source file name. For example to move file 'f.txt' to a folder 'b', destination
        should be 'b/f.txt'.

        Raises:
            File.NotFound: If source or destination key does not exist.
            File.NotADirectory: If some parent of the destination is not a directory.
        """

    @abc.abstractmethod
    async def movedir(self, at: str, to: str) -> None:
        """
        Move a folder to the destination key. The destination key should include
        source folder name. For example to move folder 'b' to a folder 'a', destination
        should be 'a/b'.

        If some parents in the destination key are missing, they will be created.
        If source key doesn't exists, it will act as a no-op.

        Raises:
            File.NotADirectory: If some parent of the destination is not a directory.
        """

    @abc.abstractmethod
    async def save(self, key: str, content: IBlobContent) -> StorageFile:
        """
        Save content to a given key.

        Raises:
            File.NotADirectory: If some parent is not a directory.
        """
