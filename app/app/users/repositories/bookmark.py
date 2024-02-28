from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterable
    from uuid import UUID

    from app.app.users.domain import Bookmark


class IBookmarkRepository(Protocol):
    async def delete_batch(self, bookmarks: Iterable[Bookmark]) -> None:
        """Delete multiple bookmarks at once."""

    async def list_all(self, user_id: UUID) -> list[Bookmark]:
        """
        Lists all bookmarks for a given user ID.

        Raises:
            User.NotFound: If a user associated with a bookmark does not exist.
        """

    async def save_batch(self, bookmarks: Iterable[Bookmark]) -> list[Bookmark]:
        """Saves multiple bookmarks to a database."""
