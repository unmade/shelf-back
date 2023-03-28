from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.app.users.domain import Bookmark

if TYPE_CHECKING:
    from app.app.users.repositories import IBookmarkRepository
    from app.typedefs import StrOrUUID

    class IServiceDatabase(Protocol):
        bookmark: IBookmarkRepository


class BookmarkService:
    __slots__ = ["db"]

    def __init__(self, database: IServiceDatabase):
        self.db = database

    async def add_bookmark(self, user_id: StrOrUUID, file_id: str) -> Bookmark:
        """
        Adds a file to user bookmarks.

        Args:
            user_id (StrOrUUID): Target user ID.
            file_id (str): Target file ID.

        Returns:
            list[Bookmark]: A saved bookmark.

        Raises:
            User.NotFound: If user with a ID does not exist.
        """
        bookmark = Bookmark(user_id=str(user_id), file_id=file_id)
        return await self.db.bookmark.save(bookmark)

    async def list_bookmarks(self, user_id: StrOrUUID) -> list[Bookmark]:
        """
        Lists bookmarks for a given user ID.

        Args:
            user_id (StrOrUUID): User ID to list bookmarks for.

        Raises:
            User.NotFound: If User with given ID does not exist.

        Returns:
            list[Bookmark]: List of resource IDs bookmarked by user.
        """
        return await self.db.bookmark.list_all(user_id)

    async def remove_bookmark(self, user_id: StrOrUUID, file_id: str) -> None:
        """
        Removes a file from user bookmarks.

        Args:
            user_id (StrOrUUID): Target user ID.
            file_id (str): Target file ID.

        Raises:
            User.NotFound: If User with a target user_id does not exist.
        """
        bookmark = Bookmark(user_id=str(user_id), file_id=file_id)
        await self.db.bookmark.delete(bookmark)
