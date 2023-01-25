from __future__ import annotations

import contextlib
import os
from pathlib import PurePath
from typing import IO, TYPE_CHECKING, Protocol

from app import errors, hashes, mediatypes, metadata
from app.app.infrastructure import IDatabase
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
    from app.typedefs import StrOrPath

__all__ = ["NamespaceService"]


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

        next_path = await self.db.file.next_path(ns_path, path)
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

    async def get_by_path(self, path) -> Namespace:
        return await self.db.namespace.get_by_path(path)

    async def get_space_used_by_owner_id(self, owner_id: UUID) -> int:
        return await self.db.namespace.get_space_used_by_owner_id(owner_id)
