from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import UUID

from app.app.files.domain import FilePendingDeletion
from app.app.files.repositories import IFilePendingDeletionRepository

if TYPE_CHECKING:
    from app.infrastructure.database.edgedb.typedefs import GelAnyConn, GelContext


def _from_db(obj) -> FilePendingDeletion:
    return FilePendingDeletion(
        id=obj.id,
        ns_path=obj.ns_path,
        path=obj.path,
        chash=obj.chash,
        mediatype=obj.mediatype,
        created_at=obj.created_at,
    )


class FilePendingDeletionRepository(IFilePendingDeletionRepository):
    def __init__(self, db_context: GelContext):
        self.db_context = db_context

    @property
    def conn(self) -> GelAnyConn:
        return self.db_context.get()

    async def delete_by_id_batch(
        self, ids: Sequence[UUID]
    ) -> list[FilePendingDeletion]:
        query = """
            SELECT (
                DELETE
                    FilePendingDeletion
                FILTER
                    .id IN {array_unpack(<array<uuid>>$ids)}
            ) { id, ns_path, path, chash, mediatype, created_at }
        """

        objs = await self.conn.query(query, ids=ids)
        return [_from_db(obj) for obj in objs]

    async def get_by_id_batch(self, ids: Sequence[UUID]) -> list[FilePendingDeletion]:
        query = """
            SELECT
                FilePendingDeletion { id, ns_path, path, chash, mediatype, created_at }
            FILTER
                .id IN {array_unpack(<array<uuid>>$ids)}
        """

        objs = await self.conn.query(query, ids=ids)
        return [_from_db(obj) for obj in objs]

    async def save_batch(
        self, entities: Sequence[FilePendingDeletion]
    ) -> list[FilePendingDeletion]:
        query = """
            WITH
                entries := array_unpack(<array<json>>$entries),
            SELECT (
                FOR entry IN {entries}
                UNION (
                    INSERT FilePendingDeletion {
                        ns_path := <str>entry['ns_path'],
                        path := <str>entry['path'],
                        chash := <str>entry['chash'],
                        mediatype := <str>entry['mediatype'],
                        created_at := <datetime>entry['created_at'],
                    }
                )
            ) { id, ns_path, path, chash, mediatype, created_at }
        """

        entries = [entity.model_dump_json() for entity in entities]
        objs = await self.conn.query(query, entries=entries)

        return [_from_db(obj) for obj in objs]
