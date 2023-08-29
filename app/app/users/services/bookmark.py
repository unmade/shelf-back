from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.users.domain import Bookmark

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.users.repositories import IBookmarkRepository

    class IServiceDatabase(Protocol):
        bookmark: IBookmarkRepository


class BookmarkService:
    __slots__ = ["db"]

    def __init__(self, database: IServiceDatabase):
        self.db = database

    async def add_bookmark(self, user_id: UUID, file_id: UUID) -> Bookmark:
        """
        Adds a file to user bookmarks.

        Raises:
            User.NotFound: If user with a ID does not exist.
        """
        bookmark = Bookmark(user_id=user_id, file_id=file_id)
        return await self.db.bookmark.save(bookmark)

    async def list_bookmarks(self, user_id: UUID) -> list[Bookmark]:
        """
        Lists bookmarks for a given user ID.

        Raises:
            User.NotFound: If User with given ID does not exist.
        """
        return await self.db.bookmark.list_all(user_id)

    async def remove_bookmark(self, user_id: UUID, file_id: UUID) -> None:
        """
        Removes a file from user bookmarks.

        Raises:
            User.NotFound: If User with a target user_id does not exist.
        """
        bookmark = Bookmark(user_id=user_id, file_id=file_id)
        await self.db.bookmark.delete(bookmark)
