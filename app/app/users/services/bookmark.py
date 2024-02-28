from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.users.domain import Bookmark

if TYPE_CHECKING:
    from collections.abc import Iterable
    from uuid import UUID

    from app.app.users.repositories import IBookmarkRepository

    class IServiceDatabase(Protocol):
        bookmark: IBookmarkRepository


class BookmarkService:
    __slots__ = ["db"]

    def __init__(self, database: IServiceDatabase):
        self.db = database

    async def add_batch(self, user_id: UUID, file_ids: Iterable[UUID]) -> None:
        """Adds multiple files to user bookmarks."""
        bookmarks = [
            Bookmark(user_id=user_id, file_id=file_id)
            for file_id in file_ids
        ]
        await self.db.bookmark.save_batch(bookmarks)

    async def list_bookmarks(self, user_id: UUID) -> list[Bookmark]:
        """
        Lists bookmarks for a given user ID.

        Raises:
            User.NotFound: If User with given ID does not exist.
        """
        return await self.db.bookmark.list_all(user_id)

    async def remove_batch(self, user_id: UUID, file_ids: Iterable[UUID]) -> None:
        """Removes multiple files from user bookmarks."""
        bookmarks = [
            Bookmark(user_id=user_id, file_id=file_id)
            for file_id in file_ids
        ]
        await self.db.bookmark.delete_batch(bookmarks)
