from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Protocol

from app.domain.entities import SENTINEL_ID, SharedLink

if TYPE_CHECKING:
    from app.app.repositories.shared_link import ISharedLinkRepository

    class IServiceDatabase(Protocol):
        shared_link: ISharedLinkRepository


class SharingService:
    """A service to share files."""

    __slots__ = ["db"]

    def __init__(self, database: IServiceDatabase):
        self.db = database

    async def get_or_create_shared_link(self, file_id: str) -> SharedLink:
        """
        Creates a shared link for a file at a given path. If the link already exists,
        then existing link will be returned.

        Args:
            file_id (str): Target file ID to share.

        Raises:
            FileNotFound: If file/folder with a given path does not exists.

        Returns:
            SharedLink: A shared link.
        """
        link = SharedLink(
            id=SENTINEL_ID,
            file_id=file_id,
            token=secrets.token_urlsafe(16),
        )
        return await self.db.shared_link.save(link)

    async def revoke_shared_link(self, token: str) -> None:
        """
        Revokes shared link token.

        Args:
            token (str): Shared link token to revoke.
        """
        await self.db.shared_link.delete(token)
