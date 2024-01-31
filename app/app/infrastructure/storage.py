from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Protocol, Self

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable, Iterator

    from app.app.files.domain import AnyPath, IFileContent

__all__ = ["IStorage", "StorageFile"]


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
        raise NotImplementedError()  # pragma: no cover

    @abc.abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        raise NotImplementedError()  # pragma: no cover

    @abc.abstractmethod
    async def delete(self, ns_path: AnyPath, path: AnyPath) -> None:
        """
        Delete a file by path.

        If path does not exists or path is a directory, it will act as a no-op.
        """

    @abc.abstractmethod
    async def delete_batch(self, items: Iterable[tuple[AnyPath, AnyPath]]) -> None:
        """
        Delete multiple file by provided paths.

        If path does not exists or path is a directory, it will act as a no-op.
        """

    @abc.abstractmethod
    async def deletedir(self, ns_path: AnyPath, path: AnyPath) -> None:
        """
        Delete a folder by path.

        If path does not exists, it will act as a no-op.
        """

    @abc.abstractmethod
    async def emptydir(self, ns_path: AnyPath, path: AnyPath) -> None:
        """
        Deletes a folder content but not a folder itself.
        """

    @abc.abstractmethod
    def download(self, ns_path: AnyPath, path: AnyPath) -> AsyncIterator[bytes]:
        """
        Return an iterator over a file content.

        Raises:
            File.NotFound: If path not found or path is a directory.
        """

    @abc.abstractmethod
    def downloaddir(self, ns_path: AnyPath, path: AnyPath) -> Iterator[bytes]:
        """
        Return an iterator over a zipped folder content.
        """

    @abc.abstractmethod
    async def exists(self, ns_path: AnyPath, path: AnyPath) -> bool:
        """
        Check whether if file exists or not in the specified path.
        """

    @abc.abstractmethod
    def iterdir(
        self,
        ns_path: AnyPath,
        path: AnyPath,
    ) -> AsyncIterator[StorageFile]:
        """
        Return an iterator of StorageFile objects for a given path.

        Raises:
            File.NotFound: If given path does not exist
            File.NotADirectory: If given path is not a directory
        """

    @abc.abstractmethod
    async def makedirs(self, ns_path: AnyPath, path: AnyPath) -> None:
        """
        Create a directory with any missing directories in a given path.

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

        Raises:
            File.NotADirectory: If some parent of the destination is not a directory.
        """

    @abc.abstractmethod
    async def save(
        self,
        ns_path: AnyPath,
        path: AnyPath,
        content: IFileContent,
    ) -> StorageFile:
        """
        Save content to a given path.

        Raises:
            File.NotADirectory: If some parent is not a directory.
        """
