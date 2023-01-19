from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.entities import SENTINEL_ID, Folder, Namespace

if TYPE_CHECKING:
    from app.app.repositories import IFolderRepository, INamespaceRepository
    from app.storage.base import Storage
    from app.typedefs import StrOrPath

__all__ = ["NamespaceService"]


class NamespaceService:
    def __init__(
        self,
        namespace_repo: INamespaceRepository,
        folder_repo: IFolderRepository,
        storage: Storage,
    ):
        self.namespace_repo = namespace_repo
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
