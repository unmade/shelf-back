from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.domain.entities import Namespace

if TYPE_CHECKING:
    from app.typedefs import StrOrUUID


class INamespaceRepository(Protocol):
    async def get_by_path(self, path: str) -> Namespace:
        """
        Returns namespace with a target path.

        Args:
            path (StrOrPath): Namespace path.

        Raises:
            errors.NamespaceNotFound: If namespace with a target path does not exists.

        Returns:
            Namespace: Namespace with a target path.
        """

    async def get_space_used_by_owner_id(self, owner_id: StrOrUUID) -> int:
        """
        Returns total space used by all namespaces owned by given `owner_id`.

        Args:
            owner_id (StrOrUUID): Namespaces owner ID.

        Returns:
            int: Space used by all namespaces by a given `owner_id`.
        """

    async def save(self, namespace: Namespace) -> Namespace:
        """
        Saves a namespace to a database.

        Args:
            namespace (Namespace): a Namespace instance.

        Raises:
            NamespaceAlreadyExists: If namespace with a given `path` already exists.

        Returns:
            Namespace: A freshly created namespace instance.
        """
