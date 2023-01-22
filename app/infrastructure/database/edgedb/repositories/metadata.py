from __future__ import annotations

from typing import TYPE_CHECKING

from app import crud
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
        await crud.metadata.create(
            self.conn,
            metadata.file_id,
            metadata.data,  # type: ignore[arg-type]
        )
