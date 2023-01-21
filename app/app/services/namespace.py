from __future__ import annotations

import contextlib
from pathlib import PurePath
from typing import TYPE_CHECKING
from uuid import UUID

from app import errors
from app.domain.entities import SENTINEL_ID, Folder, Namespace

if TYPE_CHECKING:
    from app.app.repositories import (
        IFileRepository,
        IFolderRepository,
        INamespaceRepository,
    )
    from app.storage.base import Storage
    from app.typedefs import StrOrPath

__all__ = ["NamespaceService"]


class NamespaceService:
    def __init__(
        self,
        file_repo: IFileRepository,
        folder_repo: IFolderRepository,
        namespace_repo: INamespaceRepository,
        storage: Storage,
    ):
        self.namespace_repo = namespace_repo
        self.file_repo = file_repo
        self.folder_repo = folder_repo
        self.storage = storage

    async def create(
        self,
        path: StrOrPath,
        owner_id: UUID,
    ) -> Namespace:
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
        namespace = await self.namespace_repo.save(
            Namespace(id=SENTINEL_ID, path=str(path), owner_id=owner_id)
        )

        await self.folder_repo.save(
            Folder(id=SENTINEL_ID, ns_path=namespace.path, name="home", path=".")
        )
        await self.folder_repo.save(
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

        parents = await self.file_repo.get_by_path_batch(ns_path, paths)
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
            # the second call tries to create at path 'a/b/c/d/f'. To solve that, simply
            # ignore FileAlreadyExists error.
            with contextlib.suppress(errors.FileAlreadyExists):
                await self.folder_repo.save(
                    Folder(
                        id=SENTINEL_ID,
                        ns_path=str(ns_path),
                        name=p.name,
                        path=str(p),
                    )
                )

        return await self.folder_repo.get_by_path(ns_path, path)
