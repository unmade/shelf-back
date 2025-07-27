from __future__ import annotations

from typing import TYPE_CHECKING

import gel

from app.app.files.domain import ContentMetadata, File
from app.app.files.repositories import IContentMetadataRepository
from app.toolkit import json_

if TYPE_CHECKING:
    from collections.abc import Iterable
    from uuid import UUID

    from app.infrastructure.database.gel.typedefs import GelAnyConn, GelContext

__all__ = ["ContentMetadataRepository"]


def _from_db(obj) -> ContentMetadata:
    return ContentMetadata(
        file_id=obj.file.id,
        data=json_.loads(obj.data),
    )


class ContentMetadataRepository(IContentMetadataRepository):
    def __init__(self, db_context: GelContext):
        self.db_context = db_context

    @property
    def conn(self) -> GelAnyConn:
        return self.db_context.get()

    async def get_by_file_id(self, file_id: UUID) -> ContentMetadata:
        query = """
            SELECT
                FileMetadata { data, file: { id } }
            FILTER
                .file.id = <uuid>$file_id
            LIMIT 1
        """

        try:
            obj = await self.conn.query_required_single(query, file_id=file_id)
        except gel.NoDataError as exc:
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
        except gel.MissingRequiredError as exc:
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
        except gel.MissingRequiredError as exc:
            raise File.NotFound() from exc
