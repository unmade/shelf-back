from __future__ import annotations

import itertools
import os
from pathlib import PurePath
from typing import IO, TYPE_CHECKING, Protocol

from app import timezone
from app.app.infrastructure import IDatabase
from app.domain.entities import (
    SENTINEL_ID,
    File,
    Namespace,
)

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.repositories import (
        IFileRepository,
        INamespaceRepository,
    )
    from app.typedefs import StrOrPath, StrOrUUID

    from .dupefinder import DuplicateFinderService
    from .filecore import FileCoreService

    class IServiceDatabase(IDatabase, Protocol):
        namespace: INamespaceRepository
        file: IFileRepository

__all__ = ["NamespaceService"]


class NamespaceService:
    def __init__(
        self,
        database: IServiceDatabase,
        filecore: FileCoreService,
        dupefinder: DuplicateFinderService,
    ):
        self.db = database
        self.filecore = filecore
        self.dupefinder = dupefinder

    async def add_file(
        self, ns_path: StrOrPath, path: StrOrPath, content: IO[bytes]
    ) -> File:
        """
        Saves a file to a storage and to a database. Additionally calculates and saves
        dhash and fingerprint for supported mediatypes.

        Any missing parents are also created.

        If file name is already taken, then file will be saved under a new name.
        For example - if path 'f.txt' is taken, then new path will be 'f (1).txt'.

        Args:
            ns_path (StrOrPath): Namespace path where a file should be saved.
            path (StrOrPath): Path where a file will be saved.
            content (IO): Actual file content.

        Raises:
            FileAlreadyExists: If a file in a target path already exists.
            NotADirectory: If one of the path parents is not a folder.

        Returns:
            File: Saved file.
        """
        return await self.filecore.create_file(ns_path, path, content)

    async def create(self, path: StrOrPath, owner_id: UUID) -> Namespace:
        """
        Creates a namespace with a `Home` and `Trash` folders.

        Args:
            path (StrOrPath): Namespace path.
            owner_id (UUID): Namespace owner ID.

        Raises:
            NamespaceAlreadyExists: If namespace with a given `path` already exists.

        Returns:
            Namespace: A freshly created namespace instance.
        """
        async for _ in self.db.atomic():
            ns = await self.db.namespace.save(
                Namespace(id=SENTINEL_ID, path=str(path), owner_id=owner_id)
            )
            await self.filecore.create_folder(ns.path, ".")
            await self.filecore.create_folder(ns.path, "Trash")
        return ns

    async def create_folder(self, ns_path: StrOrPath, path: StrOrPath) -> File:
        """
        Creates a folder with any missing parents in a namespace with a `ns_path`.

        Args:
            ns_path (Namespace): Namespace path where a folder should be created.
            path (StrOrPath): Path to a folder to create.

        Raises:
            FileAlreadyExists: If folder with this path already exists.
            NotADirectory: If one of the path parents is not a directory.

        Returns:
            File: Created folder.
        """
        assert str(path).lower() not in (".", "trash")
        return await self.filecore.create_folder(ns_path, path)

    async def delete_file(self, ns_path: StrOrPath, path: StrOrPath) -> File:
        """
        Permanently deletes a file. If path is a folder deletes a folder with all of its
        contents.

        Args:
            ns_path (StrOrPath): Namespace path where file/folder should be deleted.
            path (StrOrPath): Path to a file/folder to delete.

        Raises:
            FileNotFound: If a file/folder with a given path does not exists.

        Returns:
            File: Deleted file.
        """
        assert str(path).lower() not in (".", "trash"), (
            "Can't delete Home or Trash folder."
        )
        return await self.filecore.delete(ns_path, path)

    async def empty_trash(self, ns_path: StrOrPath) -> None:
        """
        Deletes all files and folders in the Trash folder in a target Namespace.

        Args:
            ns_path (StrOrPath): Namespace path where to empty the Trash folder.
        """
        await self.filecore.empty_folder(ns_path, "trash")

    async def find_duplicates(
        self, ns_path: StrOrPath, path: StrOrPath, max_distance: int = 5
    ) -> list[list[File]]:
        """
        Finds all duplicate fingerprints in a folder, including sub-folders.

        Args:
            ns_path (StrOrPath): Target namespace path.
            path (StrOrPath): Folder path where to search for fingerprints.
            max_distance (int, optional): The maximum distance at which two fingerprints
                are considered the same. Defaults to 5.

        Returns:
            list[list[File]]: List of lists of duplicate fingerprints.
        """
        groups = await self.dupefinder.find_in_folder(ns_path, path, max_distance)
        ids = itertools.chain.from_iterable(
            (fp.file_id for fp in group)
            for group in groups
        )

        files = {
            file.id: file
            for file in await self.filecore.get_by_id_batch(ns_path, ids=ids)
        }

        return [
            [files[fp.file_id] for fp in group]
            for group in groups
        ]

    async def get_by_path(self, path: str) -> Namespace:
        return await self.db.namespace.get_by_path(path)

    async def get_space_used_by_owner_id(self, owner_id: StrOrUUID) -> int:
        return await self.db.namespace.get_space_used_by_owner_id(owner_id)

    async def has_file_with_id(self, ns_path: StrOrPath, file_id: StrOrUUID) -> bool:
        """
        Checks whether a file with a given ID exists in the target namespace.

        Args:
            ns_path (StrOrPath): Target namespace path.
            file_id (StrOrUUID): Target file ID.

        Returns:
            bool: True if namespace contains file with a given ID, False otherwise.
        """
        return await self.filecore.exists_with_id(ns_path, file_id)

    async def move_file(
        self, ns_path: StrOrPath, path: StrOrPath, next_path: StrOrPath
    ) -> File:
        """
        Moves a file or a folder to a different location in the target Namespace.
        If the source path is a folder all its contents will be moved.

        Args:
            ns_path (StrOrPath): Namespace path where file/folder should be moved
            path (StrOrPath): Path to be moved.
            next_path (StrOrPath): Path that is the destination.

        Raises:
            errors.FileNotFound: If source path does not exists.
            errors.FileAlreadyExists: If some file already in the destination path.
            errors.MissingParent: If 'next_path' parent does not exists.
            errors.NotADirectory: If one of the 'next_path' parents is not a folder.

        Returns:
            File: Moved file/folder.
        """
        assert str(path).lower() not in (".", "trash"), (
            "Can't move Home or Trash folder."
        )
        return await self.filecore.move(ns_path, path, next_path)

    async def move_file_to_trash(self, ns_path: StrOrPath, path: StrOrPath) -> File:
        """
        Moves a file or folder to the Trash folder in the target Namespace.
        If path is a folder all its contents will be moved.
        If file with the same name already in the Trash, then path will be renamed.

        Args:
            db_client (DBClient): Database client.
            namespace (Namespace): Namespace where path located.
            path (StrOrPath): Path to a file or folder to be moved to the Trash folder.

        Raises:
            errors.FileNotFound: If source path does not exists.

        Returns:
            File: Moved file.
        """
        next_path = PurePath("Trash") / os.path.basename(path)

        if await self.filecore.exists_at_path(ns_path, next_path):
            name = next_path.name.strip(next_path.suffix)
            timestamp = f"{timezone.now():%H%M%S%f}"
            next_path = next_path.parent / f"{name} {timestamp}{next_path.suffix}"

        return await self.filecore.move(ns_path, path, next_path)
