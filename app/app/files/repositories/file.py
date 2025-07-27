from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Protocol,
    TypedDict,
)

from app.app.files.domain import File

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence
    from uuid import UUID

    from app.app.files.domain import AnyFile, AnyPath

__all__ = ["IFileRepository", "FileUpdate"]


class FileUpdate(TypedDict, total=False):
    ns_path: str
    name: str
    path: str
    chash: str
    size: int


class IFileRepository(Protocol):
    async def count_by_path_pattern(self, ns_path: AnyPath, pattern: str) -> int:
        """Counts the number of files with path matching the pattern."""

    async def delete(self, ns_path: AnyPath, path: AnyPath) -> File:
        """
        Deletes file at a given path.

        Raises:
            File.NotFound: If a file at a target path does not exists.
        """

    async def delete_all_with_prefix(
        self, ns_path: AnyPath, prefix: AnyPath
    ) -> None:
        """Deletes all files with path starting with a given prefix."""

    async def delete_all_with_prefix_batch(
        self, items: Mapping[str, Sequence[AnyPath]]
    ) -> None:
        """Deletes files based on specified prefixes for each namespace."""

    async def delete_batch(
        self, ns_path: AnyPath, paths: Sequence[AnyPath]
    ) -> list[File]:
        """Deletes files with given paths in the specified namespace."""

    async def exists_at_path(self, ns_path: AnyPath, path: AnyPath) -> bool:
        """Checks whether a file or a folder exists at path in a target namespace."""

    async def exists_with_id(self, ns_path: AnyPath, file_id: UUID) -> bool:
        """
        Checks whether a file or a folder with a given ID exists in a target namespace.
        """

    async def get_by_chash_batch(self, chashes: Sequence[str]) -> list[File]:
        """Returns all files with specified chashes."""

    async def get_by_id(self, file_id: UUID) -> File:
        """
        Return a file by ID.

        Raises:
            File.NotFound: If file with a given ID does not exists.
        """

    async def get_by_id_batch(self, ids: Iterable[UUID]) -> list[File]:
        """Returns all files with target IDs."""

    async def get_by_path(self, ns_path: AnyPath, path: AnyPath) -> File:
        """
        Return a file at a target path.

        Raises:
            File.NotFound: If a file with a target path does not exists.
        """

    async def get_by_path_batch(
        self, ns_path: AnyPath, paths: Iterable[AnyPath],
    ) -> list[File]:
        """Returns all files with target paths. The result is sorted by path ASC."""

    async def incr_size(
        self, ns_path: AnyPath, items: Sequence[tuple[AnyPath, int]]
    ) -> None:
        """
        Increments size for all provideded (path - size) pairs in the specified
        namespace.
        """

    async def incr_size_batch(
        self, ns_path: AnyPath, paths: Iterable[AnyPath], value: int,
    ) -> None:
        """Increments size for specified paths."""

    async def list_files(
        self,
        ns_path: AnyPath,
        *,
        included_mediatypes: Sequence[str] | None = None,
        excluded_mediatypes: Sequence[str] | None = None,
        offset: int,
        limit: int = 25,
    ) -> list[File]:
        """Lists all files in the given namespace."""

    async def list_with_prefix(
        self, ns_path: AnyPath, prefix: AnyPath
    ) -> list[AnyFile]:
        """Lists all files with a path starting with a given prefix one-level deep."""

    async def list_all_with_prefix_batch(
        self, items: Mapping[str, Sequence[AnyPath]]
    ) -> list[File]:
        """Lists files based on specified prefixes for each namespace."""

    async def replace_path_prefix(
        self, at: tuple[AnyPath, AnyPath], to: tuple[AnyPath, AnyPath]
    ) -> None:
        """Replaces `namespace` and `prefix` for all files match `at` with a `to`."""

    async def save(self, file: File) -> File:
        """
        Saves a new file.

        Raises:
            File.AlreadyExists: If a file in a target path already exists.
        """

    async def save_batch(self, files: Iterable[File]) -> None:
        """Save multiple files at once."""

    async def set_chash_batch(self, items: Iterable[tuple[UUID, str]]) -> None:
        """Sets a chash for all provideded (file ID - chash) pairs."""

    async def update(self, file: File, fields: FileUpdate) -> File:
        """
        Updates a file with provided set of fields.

        Raises:
            File.NotFound: if a file with given ID does not exists.
        """
