from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb

from app.app.users.domain import Bookmark, User
from app.app.users.repositories import IBookmarkRepository

if TYPE_CHECKING:
    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext
    from app.typedefs import StrOrUUID

__all__ = ["BookmarkRepository"]


class BookmarkRepository(IBookmarkRepository):
    def __init__(self, db_context: EdgeDBContext):
        self.db_context = db_context

    @property
    def conn(self) -> EdgeDBAnyConn:
        return self.db_context.get()

    async def delete(self, bookmark: Bookmark) -> None:
        query = """
            UPDATE
                User
            FILTER
                .id = <uuid>$user_id
            SET {
                bookmarks -= (
                    SELECT
                        File
                    FILTER
                        .id = <uuid>$file_id
                    LIMIT 1
                )
            }
        """

        try:
            await self.conn.query_required_single(
                query, user_id=bookmark.user_id, file_id=bookmark.file_id
            )
        except edgedb.NoDataError as exc:
            raise User.NotFound() from exc

    async def list_all(self, user_id: StrOrUUID) -> list[Bookmark]:
        query = """
            SELECT
                User { bookmarks }
            FILTER
                .id = <uuid>$user_id
            LIMIT 1
        """
        try:
            user = await self.conn.query_required_single(query, user_id=user_id)
        except edgedb.NoDataError as exc:
            raise User.NotFound(f"No user with id: '{user_id}'") from exc

        return [
            Bookmark(user_id=str(user_id), file_id=str(entry.id))
            for entry in user.bookmarks
        ]

    async def save(self, bookmark: Bookmark) -> Bookmark:
        query = """
            UPDATE
                User
            FILTER
                .id = <uuid>$user_id
            SET {
                bookmarks += (
                    SELECT
                        File
                    FILTER
                        .id = <uuid>$file_id
                    LIMIT 1
                )
            }
        """

        try:
            await self.conn.query_required_single(
                query, user_id=bookmark.user_id, file_id=bookmark.file_id,
            )
        except edgedb.NoDataError as exc:
            raise User.NotFound() from exc

        return bookmark
