from __future__ import annotations

import itertools
import operator
from typing import TYPE_CHECKING

import gel

from app.app.users.domain import Bookmark, User
from app.app.users.repositories import IBookmarkRepository
from app.toolkit import json_

if TYPE_CHECKING:
    from collections.abc import Iterable
    from uuid import UUID

    from app.infrastructure.database.gel.typedefs import GelAnyConn, GelContext

__all__ = ["BookmarkRepository"]


class BookmarkRepository(IBookmarkRepository):
    def __init__(self, db_context: GelContext):
        self.db_context = db_context

    @property
    def conn(self) -> GelAnyConn:
        return self.db_context.get()

    async def delete_batch(self, bookmarks: Iterable[Bookmark]) -> None:
        query = """
            WITH
                entries := array_unpack(<array<json>>$entries),
            FOR entry IN {entries}
            UNION (
                UPDATE
                    User
                FILTER
                    .id = <uuid>entry['user_id']
                SET {
                    bookmarks -= (
                        SELECT
                            File
                        FILTER
                            .id IN array_unpack(<array<uuid>>entry['file_ids'])
                    )
                }
            )
        """

        key = operator.attrgetter("user_id")
        entities = sorted(bookmarks, key=key)
        entries = [
            json_.dumps({
                "user_id": str(user_id),
                "file_ids": [str(bookmark.file_id) for bookmark in bookmarks],
            })
            for user_id, bookmarks in itertools.groupby(entities, key=key)
        ]

        await self.conn.query(query, entries=entries)

    async def list_all(self, user_id: UUID) -> list[Bookmark]:
        query = """
            SELECT
                User { bookmarks }
            FILTER
                .id = <uuid>$user_id
            LIMIT 1
        """
        try:
            user = await self.conn.query_required_single(query, user_id=user_id)
        except gel.NoDataError as exc:
            raise User.NotFound(f"No user with id: '{user_id}'") from exc

        return [
            Bookmark(user_id=user_id, file_id=entry.id)
            for entry in user.bookmarks
        ]

    async def save_batch(self, bookmarks: Iterable[Bookmark]) -> list[Bookmark]:
        query = """
            WITH
                entries := array_unpack(<array<json>>$entries),
            FOR entry IN {entries}
            UNION (
                UPDATE
                    User
                FILTER
                    .id = <uuid>entry['user_id']
                SET {
                    bookmarks += (
                        SELECT
                            File
                        FILTER
                            .id IN array_unpack(<array<uuid>>entry['file_ids'])
                    )
                }
            )
        """

        key = operator.attrgetter("user_id")
        entities = sorted(bookmarks, key=key)
        entries = [
            json_.dumps({
                "user_id": str(user_id),
                "file_ids": [str(bookmark.file_id) for bookmark in bookmarks],
            })
            for user_id, bookmarks in itertools.groupby(entities, key=key)
        ]

        await self.conn.query(query, entries=entries)
        return entities
