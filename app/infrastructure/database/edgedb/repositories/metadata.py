from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb

from app import errors
from app.app.repositories import IContentMetadataRepository

if TYPE_CHECKING:
    from app.domain.entities import ContentMetadata
    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext

__all__ = ["ContentMetadataRepository"]


class ContentMetadataRepository(IContentMetadataRepository):
    def __init__(self, db_context: EdgeDBContext):
        self.db_context = db_context

    @property
    def conn(self) -> EdgeDBAnyConn:
        return self.db_context.get()

    async def save(self, metadata: ContentMetadata) -> None:
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
        data = metadata.data.json(exclude_none=True)

        try:
            await self.conn.query_required_single(query, file_id=file_id, data=data)
        except edgedb.MissingRequiredError as exc:
            raise errors.FileNotFound() from exc
