from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Protocol

from app.app.files.domain import SharedLink
from app.app.infrastructure.database import SENTINEL_ID

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.repositories import ISharedLinkRepository

    class IServiceDatabase(Protocol):
        shared_link: ISharedLinkRepository


class SharingService:
    """A service to share files."""

    __slots__ = ["db"]

    def __init__(self, database: IServiceDatabase):
        self.db = database

    async def create_link(self, file_id: UUID) -> SharedLink:
        """
        Creates a shared link for a file at a given path. If the link already exists,
        then existing link will be returned.

        Raises:
            File.NotFound: If file/folder with a given path does not exist.
        """
        link = SharedLink(
            id=SENTINEL_ID,
            file_id=file_id,
            token=secrets.token_urlsafe(16),
        )
        return await self.db.shared_link.save(link)

    async def get_link_by_file_id(self, file_id: UUID) -> SharedLink:
        """
        Returns shared link by a given file ID.

        Args:
            file_id (UUID): File ID.

        Raises:
            SharedLink.NotFound: If file/folder with a given path does not exist.

        Returns:
            SharedLink: A SharedLink.
        """
        return await self.db.shared_link.get_by_file_id(file_id)

    async def get_link_by_token(self, token: str) -> SharedLink:
        """
        Returns shared link by a given token.

        Args:
            token (str): Target shared link token.

        Raises:
            SharedLink.NotFound: If a link with a given token does not exist.

        Returns:
            SharedLink: A SharedLink.
        """
        return await self.db.shared_link.get_by_token(token)

    async def revoke_link(self, token: str) -> None:
        """
        Revokes shared link token.

        Args:
            token (str): Shared link token to revoke.
        """
        await self.db.shared_link.delete(token)
