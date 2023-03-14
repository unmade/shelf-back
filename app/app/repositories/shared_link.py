from __future__ import annotations

from typing import Protocol

from app.domain.entities import SharedLink


class ISharedLinkRepository(Protocol):
    async def delete(self, token: str) -> None:
        """
        Deletes shared link.

        Args:
            token (str): Token to be revoked.
        """

    async def save(self, shared_link: SharedLink) -> SharedLink:
        """
        Saves shared link to the database.

        Args:
            shared_link (SharedLink): A shared link instance to save.

        Raises:
            errors.FileNotFound: If file in a given path does not exists.

        Returns:
            SharedLink: Shared link.
        """
