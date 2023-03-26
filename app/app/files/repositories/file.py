from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Iterable,
    Protocol,
    Required,
    Sequence,
    TypedDict,
)

from app.app.files.domain import File

if TYPE_CHECKING:
    from app.typedefs import StrOrPath, StrOrUUID

__all__ = ["IFileRepository", "FileUpdate"]


class FileUpdate(TypedDict, total=False):
    id: Required[str]
    name: str
    path: str
    size: int


class IFileRepository(Protocol):
    async def count_by_path_pattern(self, ns_path: StrOrPath, pattern: str) -> int:
        """
        Counts the number of files with path matching the pattern.

        Args:
            ns_path (StrOrPath): Target namespace path.
            pattern (str): Path pattern.

        Returns:
            int: Number of occurences that matches the pattern.
        """
    async def delete(self, ns_path: StrOrPath, path: StrOrPath) -> File:
        """
        Deletes file at a given path.

        Args:
            ns_path (StrOrPath): Target namespace path.
            paths (StrOrPath): Path to be deleted.

        Raises:
            File.NotFound: If a file at a target path does not exists.

        Returns:
            File: Deleted file.
        """

    async def delete_all_with_prefix(
        self, ns_path: StrOrPath, prefix: StrOrPath
    ) -> None:
        """
        Deletes all files with path starting with a given prefix.

        Args:
            ns_path (StrOrPath): Target namespace path.
            paths (StrOrPath): Path to be deleted.
        """

    async def exists_at_path(self, ns_path: StrOrPath, path: StrOrPath) -> bool:
        """
        Checks whether a file or a folder exists at path in a target namespace.

        Args:
            ns_path (StrOrPath): Target namespace path.
            path (StrOrPath): Path to a file or a folder.

        Returns:
            bool: True if file/folder exists, False otherwise.
        """
    async def exists_with_id(self, ns_path: StrOrPath, file_id: StrOrUUID) -> bool:
        """
        Checks whether a file or a folder with a given ID exists in a target namespace.

        Args:
            ns_path (StrOrPath): Target namespace path.
            file_id (StrOrUUID): File ID.

        Returns:
            bool: True if file/folder exists, False otherwise.
        """

    async def get_by_id(self, file_id: str) -> File:
        """
        Return a file by ID.

        Args:
            file_id (StrOrUUID): File ID.

        Raises:
            File.NotFound: If file with a given ID does not exists.

        Returns:
            File: File with a target ID.
        """

    async def get_by_id_batch(
        self, ns_path: StrOrPath, ids: Iterable[StrOrUUID]
    ) -> list[File]:
        """
        Returns all files with target IDs.

        Args:
            ns_path (StrOrPath): Namespace where files are located.
            ids (Iterable[StrOrUUID]): Iterable of paths to look for.

        Returns:
            List[File]: Files with target IDs.
        """

    async def get_by_path(self, ns_path: StrOrPath, path: StrOrPath) -> File:
        """
        Return a file at a target path.

        Args:
            ns_path (StrOrPath): Namespace path where a file is located.
            path (StrOrPath): Path to a file.

        Raises:
            File.NotFound: If a file with a target path does not exists.

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
        self, ns_path: StrOrPath, paths: Iterable[StrOrPath], value: int,
    ) -> None:
        """
        Increments size for specified paths.

        Args:
            ns_path (str): Namespace.
            paths (Iterable[StrOrPath]): List of path which size will be incremented.
            value (int): value that will be added to the current file size.
        """

    async def list_by_mediatypes(
        self,
        ns_path: StrOrPath,
        mediatypes: Sequence[str],
        *,
        offset: int,
        limit: int = 25,
    ) -> list[File]:
        """
        Lists all files of a given mediatypes.

        Args:
            ns_path (StrOrPath): Target namespace where files should be listed.
            mediatypes (Iterable[str]): List of mediatypes that files should match.
            offset (int): Skip this number of elements.
            limit (int, optional): Include only the first element-count elements.

        Returns:
            list[File]: list of Files
        """

    async def list_with_prefix(
        self, ns_path: StrOrPath, prefix: StrOrPath
    ) -> list[File]:
        """
        Lists all files with a path starting with a given prefix.

        Args:
            ns_path (StrOrPath): Target namespace where files should be listed.
            prefix (StrOrPath): Target prefix.

        Returns:
            list[File]: List of all files/folders with a target prefix.
        """

    async def replace_path_prefix(
        self, ns_path: StrOrPath, prefix: StrOrPath, next_prefix: StrOrPath
    ) -> None:
        """
        Replaces `prefix` with a `next_prefix` for all paths starting with a `prefix`.

        Args:
            ns_path (StrOrPath): Namespace path.
            prefix (StrOrPath): Prefix to be replaced.
            next_prefix (StrOrPath): Prefix to be replaces to.
        """

    async def save(self, file: File) -> File:
        """
        Saves a new file.

        Args:
            file (File): a File to be saved.

        Raises:
            File.AlreadyExists: If a file in a target path already exists.

        Returns:
            File: Created file.
        """

    async def save_batch(self, files: Iterable[File]) -> None:
        """
        Save multiple files at once.

        Args:
            files (Iterable[File]): Iterable of files to be saved.
        """

    async def update(self, file_update: FileUpdate) -> File:
        """
        Updates a file with provided set of fields.

        Args:
            file (FileUpdate): a file fields to be updated with new values.

        Raises:
            File.NotFound: if a file with given ID does not exists.

        Returns:
            File: Updated file.
        """
