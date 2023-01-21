from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Protocol

from app.domain.entities import Folder

if TYPE_CHECKING:
    from app.typedefs import StrOrPath


class IFolderRepository(Protocol):
    async def get_by_path(self, ns_path: StrOrPath, path: StrOrPath) -> Folder:
        """
        Return a folder with a target path.

        Args:
            ns_path (StrOrPath): Namespace path where a folder is located.
            path (StrOrPath): Path to a folder.

        Raises:
            FileNotFound: If a folder with a target path does not exists.

        Returns:
            Folder: Folder with a target path.
        """

    async def get_by_path_batch(
        self, ns_path: StrOrPath, paths: Iterable[StrOrPath],
    ) -> list[Folder]:
        """
        Return all folders with target paths. The result is sorted by path ASC.

        Args:
            ns_path (StrOrPath): Namespace path where files are located.
            paths (Iterable[StrOrPath]): Iterable of paths to look for.

        Returns:
            List[Folder]: List of folders with target paths.
        """

    async def save(self, folder: Folder) -> Folder:
        """
        Saves a folder to a database.

        Args:
            folder (Folder): a Folder instance to save.

        Raises:
            FileAlreadyExists: If file in a target path already exists.
            MissingParent: If target path does not have a parent.
            NotADirectory: If parent path is not a directory.

        Returns:
            Folder: Created folder.
        """
