from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.files.domain import SENTINEL_ID, Namespace
from app.app.infrastructure import IDatabase

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.repositories import INamespaceRepository
    from app.typedefs import StrOrPath, StrOrUUID

    class IServiceDatabase(IDatabase, Protocol):
        namespace: INamespaceRepository

__all__ = ["NamespaceService"]


class NamespaceService:
    __slots__ = ["db"]

    def __init__(self, database: IServiceDatabase):
        self.db = database

    async def create(self, path: StrOrPath, owner_id: UUID) -> Namespace:
        """
        Creates a namespace.

        Args:
            path (StrOrPath): Namespace path.
            owner_id (UUID): Namespace owner ID.

        Raises:
            NamespaceAlreadyExists: If namespace with a given `path` already exists.

        Returns:
            Namespace: A freshly created namespace instance.
        """
        return await self.db.namespace.save(
            Namespace(id=SENTINEL_ID, path=str(path), owner_id=owner_id)
        )

    async def get_by_owner_id(self, owner_id: StrOrUUID) -> Namespace:
        """
        Returns a namespace with a given owner ID.

        Args:
            owner_id (StrOrUUID): Namespace owner ID.

        Raises:
            Namespace.NotFound: If namespace with a given owner ID does not exist.

        Returns:
            Namespace: A namespace with a target owner ID.
        """
        return await self.db.namespace.get_by_owner_id(owner_id)

    async def get_by_path(self, path: str) -> Namespace:
        """
        Returns namespace with a target path.

        Args:
            path (StrOrPath): Namespace path.

        Raises:
            Namespace.NotFound: If namespace with a target path does not exist.

        Returns:
            Namespace: Namespace with a target path.
        """
        return await self.db.namespace.get_by_path(path)

    async def get_space_used_by_owner_id(self, owner_id: StrOrUUID) -> int:
        """
        Returns total space used by all namespaces owned by given `owner_id`.

        Args:
            owner_id (StrOrUUID): Namespaces owner ID.

        Returns:
            int: Space used by all namespaces by a given `owner_id`.
        """
        return await self.db.namespace.get_space_used_by_owner_id(owner_id)
