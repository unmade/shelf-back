from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.domain import SharedLink


class ISharedLinkRepository(Protocol):
    async def delete(self, token: str) -> None:
        """Deletes shared link."""

    async def get_by_file_id(self, file_id: UUID) -> SharedLink:
        """
        Returns shared link by a given file ID.

        Raises:
            SharedLink.NotFound: If file/folder with a given path does not exist.
        """

    async def get_by_token(self, token: str) -> SharedLink:
        """
        Returns a shared link by token.

        Raises:
            SharedLink.NotFound: If a link with a given token does not exist.
        """

    async def list_by_ns(
        self, ns_path: str, *, offset: int = 0, limit: int = 25
    ) -> list[SharedLink]:
        """List shared links in the given namespace."""

    async def save(self, shared_link: SharedLink) -> SharedLink:
        """
        Saves shared link to the database.

        Raises:
            File.NotFound: If file in a given path does not exist.
        """
