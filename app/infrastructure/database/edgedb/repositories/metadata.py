from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

import edgedb

from app.app.files.domain import ContentMetadata, File
from app.app.files.repositories import IContentMetadataRepository
from app.toolkit import json_

if TYPE_CHECKING:
    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext

__all__ = ["ContentMetadataRepository"]


def _from_db(obj) -> ContentMetadata:
    return ContentMetadata(
        file_id=str(obj.file.id),
        data=json_.loads(obj.data),
    )


class ContentMetadataRepository(IContentMetadataRepository):
    def __init__(self, db_context: EdgeDBContext):
        self.db_context = db_context

    @property
    def conn(self) -> EdgeDBAnyConn:
        return self.db_context.get()

    async def get_by_file_id(self, file_id: str) -> ContentMetadata:
        query = """
            SELECT
                FileMetadata { data, file: { id } }
            FILTER
                .file.id = <uuid>$file_id
            LIMIT 1
        """

        try:
            obj = await self.conn.query_required_single(query, file_id=file_id)
        except edgedb.NoDataError as exc:
            raise ContentMetadata.NotFound() from exc

        return _from_db(obj)

    async def save(self, metadata: ContentMetadata) -> ContentMetadata:
        query = """
            INSERT FileMetadata {
                data := <json>$data,
                file := (
                    SELECT File
                    FILTER .id = <uuid>$file_id
                    LIMIT 1
                )
            }
        """

        file_id = metadata.file_id
        data = metadata.data.model_dump_json(exclude_none=True)

        try:
            await self.conn.query_required_single(query, file_id=file_id, data=data)
        except edgedb.MissingRequiredError as exc:
            raise File.NotFound() from exc

        return metadata

    async def save_batch(self, metadatas: Iterable[ContentMetadata]):
        query = """
            WITH
                entries := array_unpack(<array<json>>$entries),
            FOR entry IN {entries}
            UNION (
                INSERT FileMetadata {
                    data := entry['data'],
                    file := (
                        SELECT
                            File
                        FILTER
                            .id = <uuid>entry['file_id']
                    )
                }
                UNLESS CONFLICT
            )
        """

        entries = [
            json_.dumps({
                "file_id": str(metadata.file_id),
                "data": metadata.data.model_dump(exclude_none=True),
            })
            for metadata in metadatas
        ]

        try:
            await self.conn.query(query, entries=entries)
        except edgedb.MissingRequiredError as exc:
            raise File.NotFound() from exc
