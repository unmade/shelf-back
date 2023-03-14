from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb

from app import errors
from app.app.repositories import ISharedLinkRepository
from app.domain.entities import SharedLink

if TYPE_CHECKING:
    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext

__all__ = ["SharedLinkRepository"]


class SharedLinkRepository(ISharedLinkRepository):
    def __init__(self, db_context: EdgeDBContext):
        self.db_context = db_context

    @property
    def conn(self) -> EdgeDBAnyConn:
        return self.db_context.get()

    async def delete(self, token: str) -> None:
        query = """
            DELETE
                SharedLink
            FILTER
                .token = <str>$token
        """

        await self.conn.query_single(query, token=token)

    async def save(self, shared_link: SharedLink) -> SharedLink:
        query = """
            SELECT (
                INSERT SharedLink {
                    token := <str>$token,
                    file := (
                        SELECT
                            File
                        FILTER
                            .id = <uuid>$file_id
                    )
                }
                UNLESS CONFLICT ON .file
                ELSE (
                    SELECT
                        SharedLink
                )
            ) { id, token }
        """

        try:
            link = await self.conn.query_required_single(
                query,
                file_id=shared_link.file_id,
                token=shared_link.token,
            )
        except edgedb.MissingRequiredError as exc:
            raise errors.FileNotFound() from exc

        return shared_link.copy(update={"id": link.id})
