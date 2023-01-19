from __future__ import annotations

from typing import Protocol

from app.domain.entities import Namespace


class INamespaceRepository(Protocol):
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
