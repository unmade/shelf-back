from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb

from app.app.files.domain import File, SharedLink
from app.app.files.repositories import ISharedLinkRepository

if TYPE_CHECKING:
    from uuid import UUID

    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext

__all__ = ["SharedLinkRepository"]


def _from_db(obj) -> SharedLink:
    return SharedLink(
        id=obj.id,
        file_id=obj.file.id,
        token=obj.token,
        created_at=obj.created_at,
    )


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

    async def get_by_file_id(self, file_id: UUID) -> SharedLink:
        query = """
            SELECT
                SharedLink { id, token, created_at, file: { id } }
            FILTER
                .file.id = <uuid>$file_id
            LIMIT 1
        """

        try:
            link = await self.conn.query_required_single(query, file_id=file_id)
        except edgedb.NoDataError as exc:
            raise SharedLink.NotFound from exc

        return _from_db(link)

    async def get_by_token(self, token: str) -> SharedLink:
        query = """
            SELECT
                SharedLink { id, token, created_at, file: { id } }
            FILTER
                .token = <str>$token
        """

        try:
            link = await self.conn.query_required_single(query, token=token)
        except edgedb.NoDataError as exc:
            raise SharedLink.NotFound from exc

        return _from_db(link)

    async def list_by_ns(
        self, ns_path: str, *, offset: int = 0, limit: int = 25
    ) -> list[SharedLink]:
        query = """
            SELECT
                SharedLink { id, token, created_at, file: { id } }
            FILTER
                .file.namespace.path = <str>$ns_path
        """

        objs = await self.conn.query(query, ns_path=ns_path)
        return [_from_db(obj) for obj in objs]

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
                    ),
                    created_at := <datetime>$created_at
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
                created_at=shared_link.created_at,
            )
        except edgedb.MissingRequiredError as exc:
            raise File.NotFound() from exc

        return shared_link.model_copy(update={"id": link.id})
