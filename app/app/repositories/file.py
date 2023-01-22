from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Protocol

from app.domain.entities import File

if TYPE_CHECKING:
    from app.typedefs import StrOrPath


class IFileRepository(Protocol):
    async def get_by_path(self, ns_path: StrOrPath, path: StrOrPath) -> File:
        """
        Return a file at a target path.

        Args:
            ns_path (StrOrPath): Namespace path where a file is located.
            path (StrOrPath): Path to a file.

        Raises:
            FileNotFound: If a file with a target path does not exists.

        Returns:
            File: File with at a target path.
        """

    async def get_by_path_batch(
        self, ns_path: StrOrPath, paths: Iterable[StrOrPath],
    ) -> list[File]:
        """
        Returns all files with target paths. The result is sorted by path ASC.

        Args:
            ns_path (StrOrPath): Namespace path where files are located.
            paths (Iterable[StrOrPath]): Iterable of paths to look for.

        Returns:
            list[File]: List of files with target paths.
        """

    async def incr_size_batch(
        self, ns_path: str, paths: Iterable[StrOrPath], value: int,
    ) -> None:
        """
        Increments size for specified paths.

        Args:
            ns_path (str): Namespace.
            paths (Iterable[StrOrPath]): List of path which size will be incremented.
            value (int): value that will be added to the current file size.
        """

    async def next_path(self, ns_path: StrOrPath, path: StrOrPath) -> str:
        """
        Return a path with modified name if current one already taken, otherwise return
        path unchanged.

        For example, if path 'a/f.tar.gz' exists, then the next path will be as follows
        'a/f (1).tar.gz'.

        Args:
            ns_path (StrOrPath): Namespace path where to look for a path.
            path (StrOrPath): Target path.

        Returns:
            str: an available file path
        """

    async def save(self, file: File) -> File:
        """
        Saves a new file.

        Args:
            file (File): a File to be saved

        Raises:
            FileAlreadyExists: If a file in a target path already exists.

        Returns:
            File: Created file.
        """
