from __future__ import annotations

import contextlib
import os
from pathlib import PurePath
from typing import IO, TYPE_CHECKING, Any, Iterable, Iterator, Protocol

from app import errors, hashes, mediatypes, metadata, timezone
from app.app.infrastructure import IDatabase
from app.app.repositories.file import FileUpdate
from app.domain.entities import (
    SENTINEL_ID,
    ContentMetadata,
    File,
    Fingerprint,
    Folder,
    Namespace,
)

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.infrastructure.storage import IStorage
    from app.app.repositories import (
        IContentMetadataRepository,
        IFileRepository,
        IFingerprintRepository,
        IFolderRepository,
        INamespaceRepository,
    )
    from app.typedefs import StrOrPath, StrOrUUID

__all__ = ["NamespaceService"]


def _lowered(items: Iterable[Any]) -> Iterator[str]:
    """Return an iterator of lower-cased strings."""
    return (str(item).lower() for item in items)


class IServiceDatabase(IDatabase, Protocol):
    file: IFileRepository
    fingerprint: IFingerprintRepository
    folder: IFolderRepository
    metadata: IContentMetadataRepository
    namespace: INamespaceRepository


class NamespaceService:
    def __init__(self, database: IServiceDatabase, storage: IStorage):
        self.db = database
        self.storage = storage

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

        path = PurePath(path)
        try:
            parent = await self.db.file.get_by_path(ns_path, path.parent)
        except errors.FileNotFound:
            with contextlib.suppress(errors.FileAlreadyExists):
                await self.create_folder(ns_path, str(path.parent))
        else:
            if not parent.is_folder():
                raise errors.NotADirectory()

        next_path = await self.get_available_path(ns_path, path)
        mediatype = mediatypes.guess(next_path, content)

        dhash = hashes.dhash(content, mediatype=mediatype)
        meta = metadata.load(content, mediatype=mediatype)

        storage_file = await self.storage.save(ns_path, next_path, content)

        async for _ in self.db.atomic(attempts=10):
            file = await self.db.file.save(
                File(
                    id=SENTINEL_ID,
                    ns_path=str(ns_path),
                    name=os.path.basename(next_path),
                    path=next_path,
                    size=storage_file.size,
                    mediatype=mediatype,
                ),
            )
            if dhash is not None:
                await self.db.fingerprint.save(Fingerprint(file.id, value=dhash))
            if meta is not None:
                await self.db.metadata.save(
                    ContentMetadata(
                        file_id=str(file.id),
                        data=meta,  # type: ignore[arg-type]
                    ),
                )
            await self.db.file.incr_size_batch(ns_path, path.parents, file.size)

        return file

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
        await self.storage.makedirs(path, "Trash")
        namespace = await self.db.namespace.save(
            Namespace(id=SENTINEL_ID, path=str(path), owner_id=owner_id)
        )

        await self.db.folder.save(
            Folder(id=SENTINEL_ID, ns_path=namespace.path, name="home", path=".")
        )
        await self.db.folder.save(
            Folder(id=SENTINEL_ID, ns_path=namespace.path, name="Trash", path="Trash")
        )

        return namespace

    async def create_folder(self, ns_path: StrOrPath, path: StrOrPath) -> Folder:
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
        paths = [PurePath(path)] + list(PurePath(path).parents)

        parents = await self.db.file.get_by_path_batch(ns_path, paths)
        assert len(parents) > 0, f"No home folder in a namespace: '{ns_path}'"

        if any(not file.is_folder() for file in parents):
            raise errors.NotADirectory()
        if parents[-1].path.lower() == str(path).lower():
            raise errors.FileAlreadyExists()

        await self.storage.makedirs(ns_path, path)

        paths_lower = [str(p).lower() for p in paths]
        index = paths_lower.index(parents[-1].path.lower())

        for p in reversed(paths[:index]):
            # parallel calls can create folder at the same path. Consider, for example,
            # when the first call tries to create a folder at path 'a/b/c/f' and
            # the second call tries to create at path 'a/b/c/d/f'. To solve that,
            # simply ignore FileAlreadyExists error.
            with contextlib.suppress(errors.FileAlreadyExists):
                await self.db.folder.save(
                    Folder(
                        id=SENTINEL_ID,
                        ns_path=str(ns_path),
                        name=p.name,
                        path=str(p),
                    )
                )

        return await self.db.folder.get_by_path(ns_path, path)

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

        async for _ in self.db.atomic():
            file = await self.db.file.delete(ns_path, path)
            if file.is_folder():
                await self.db.file.delete_all_with_prefix(ns_path, prefix=file.path)
            parents = PurePath(file.path).parents
            await self.db.file.incr_size_batch(ns_path, parents, value=-file.size)

        storage = self.storage
        delete_from_storage = storage.deletedir if file.is_folder() else storage.delete
        await delete_from_storage(ns_path, path)

        return file

    async def empty_trash(self, ns_path: StrOrPath) -> None:
        """
        Deletes all files and folders in the Trash folder in a target Namespace.

        Args:
            ns_path (StrOrPath): Namespace path where to empty the Trash folder.
        """
        trash = await self.db.file.get_by_path(ns_path, "trash")
        if trash.size == 0:
            return

        async for _ in self.db.atomic():
            await self.db.file.delete_all_with_prefix(ns_path, "trash")
            parents = [".", "trash"]
            await self.db.file.incr_size_batch(ns_path, parents, value=-trash.size)
        await self.storage.emptydir(ns_path, "trash")

    async def get_available_path(self, ns_path: StrOrPath, path: StrOrPath) -> str:
        """
        Returns a path with modified name if the current one is already taken, otherwise
        returns path unchanged.

        For example, if path 'a/f.tar.gz' exists, then the next path will be as follows
        'a/f (1).tar.gz'.

        Args:
            ns_path (StrOrPath): Namespace path where to look for a path.
            path (StrOrPath): Target path.

        Returns:
            str: an available file path
        """
        if not await self.db.file.exists_at_path(ns_path, path):
            return str(path)

        suffix = "".join(PurePath(path).suffixes)
        stem = str(path)[:len(str(path)) - len(suffix)]
        pattern = f"{stem} \\([[:digit:]]+\\){suffix}"
        count = await self.db.file.count_by_path_pattern(ns_path, pattern)
        return f"{stem} ({count + 1}){suffix}"

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
        return await self.db.file.exists_with_id(ns_path, file_id)

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
        path = PurePath(path)
        next_path = PurePath(next_path)

        assert str(path).lower() not in (".", "trash"), (
            "Can't move Home or Trash folder."
        )
        assert not str(next_path).lower().startswith(f"{str(path).lower()}/"), (
            "Can't move to itself."
        )

        paths = [path, next_path, next_path.parent]
        files = {
            file.path.lower(): file
            for file in await self.db.file.get_by_path_batch(ns_path, paths)
        }

        file = files.get(str(path).lower())
        if file is None:
            raise errors.FileNotFound() from None

        if str(next_path.parent).lower() not in files:
            raise errors.MissingParent() from None

        next_parent = files[str(next_path.parent).lower()]
        if not next_parent.is_folder():
            raise errors.NotADirectory() from None

        if str(path).lower() != str(next_path).lower():
            if str(next_path).lower() in files:
                raise errors.FileAlreadyExists() from None

        # preserve parent casing
        next_path = PurePath(next_parent.path) / next_path.name
        return await self._move_file(file, next_path)

    async def move_file_to_trash(self, ns_path: StrOrPath, path: StrOrPath) -> File:
        """
        Move a file or folder to the Trash folder in the target Namespace.
        If the path is a folder all its contents will be moved.
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

        file = await self.db.file.get_by_path(ns_path, path)

        if await self.db.file.exists_at_path(ns_path, next_path):
            name = next_path.name.strip(next_path.suffix)
            timestamp = f"{timezone.now():%H%M%S%f}"
            next_path = next_path.parent / f"{name} {timestamp}{next_path.suffix}"

        return await self._move_file(file, next_path)

    async def _move_file(self, file: File, next_path: StrOrPath) -> File:
        """Actually moves a file or a folder in the storage and in the database."""
        ns_path = file.ns_path
        path = PurePath(file.path)
        next_path = PurePath(next_path)

        to_decrease = set(_lowered(path.parents)) - set(_lowered(next_path.parents))
        to_increase = set(_lowered(next_path.parents)) - set(_lowered(path.parents))

        file_update = FileUpdate(
            id=file.id,
            name=next_path.name,
            path=str(next_path),
        )

        move_storage = self.storage.movedir if file.is_folder() else self.storage.move
        await move_storage(ns_path, file.path, file_update["path"])
        async for _ in self.db.atomic():
            updated_file = await self.db.file.update(file_update)
            if file.is_folder():
                await self.db.file.replace_path_prefix(ns_path, path, next_path)
            await self.db.file.incr_size_batch(ns_path, to_decrease, value=-file.size)
            await self.db.file.incr_size_batch(ns_path, to_increase, value=file.size)
        return updated_file
