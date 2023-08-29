from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.users.domain import Bookmark


class IBookmarkRepository(Protocol):
    async def delete(self, bookmark: Bookmark) -> None:
        """
        Deletes a bookmark.

        Args:
            bookmark (Bookmark): A bookmark to remove.

        Raises:
            Bookmark.NotFound: If bookmark does not exist.
        """

    async def list_all(self, user_id: UUID) -> list[Bookmark]:
        """
        Lists all bookmarks for a given user ID.

        Args:
            user_id (UUID): User ID to list bookmarks for.

        Raises:
            User.NotFound: If a user associated with a bookmark does not exist.

        Returns:
            list[Bookmark]: List of all user bookmarks.
        """

    async def save(self, bookmark: Bookmark) -> Bookmark:
        """
        Saves a user bookmark.

        If file with a given file ID does not exist, then it acts as no-op.

        Args:
            bookmark (Bookmark): A bookmark to save.

        Raises:
            User.NotFound: If a user associated with a bookmark does not exist.
        """
