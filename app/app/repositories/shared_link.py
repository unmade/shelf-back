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

    async def get_by_file_id(self, file_id: str) -> SharedLink:
        """
        Returns shared link by a given file ID.

        Args:
            file_id (str): File ID.

        Raises:
            SharedLinkNotFound: If file/folder with a given path does not exist.

        Returns:
            SharedLink: A SharedLink.
        """

    async def get_by_token(self, token: str) -> SharedLink:
        """
        Returns a shared link by token.

        Args:
            token (str): Link token.

        Raises:
            SharedLinkNotFound: If a link with a given token does not exist.

        Returns:
            SharedLink: A SharedLink.
        """

    async def save(self, shared_link: SharedLink) -> SharedLink:
        """
        Saves shared link to the database.

        Args:
            shared_link (SharedLink): A shared link instance to save.

        Raises:
            errors.FileNotFound: If file in a given path does not exist.

        Returns:
            SharedLink: Shared link.
        """
