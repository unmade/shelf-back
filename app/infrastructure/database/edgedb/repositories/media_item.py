from __future__ import annotations

from typing import TYPE_CHECKING

from app.app.photos.domain import MediaItem
from app.app.photos.repositories import IMediaItemRepository
from app.config import config

if TYPE_CHECKING:
    from uuid import UUID

    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext

__all__ = ["MediaItemRepository"]


def _from_db(obj) -> MediaItem:
    return MediaItem(
        file_id=obj.id,
        name=obj.name,
        size=obj.size,
        mtime=obj.mtime,
        mediatype=obj.mediatype.name
    )


class MediaItemRepository(IMediaItemRepository):
    def __init__(self, db_context: EdgeDBContext):
        self.db_context = db_context

    @property
    def conn(self) -> EdgeDBAnyConn:
        return self.db_context.get()

    async def list_by_user_id(
        self,
        user_id: UUID,
        *,
        offset: int,
        limit: int = 25,
    ) -> list[MediaItem]:
        query = """
            WITH
                namespace := (
                    SELECT
                        Namespace
                    FILTER
                        .owner.id = <uuid>$user_id
                ),
                mediatypes := (
                    SELECT
                        MediaType
                    FILTER
                        .name IN {array_unpack(<array<str>>$mediatypes)}
                )
            SELECT
                File { id, name, size, mtime, mediatype: { name } }
            FILTER
                .path ilike <str>$path ++ '%'
                AND
                .namespace = namespace
                AND
                .mediatype IN mediatypes
            ORDER BY
                .mtime DESC
            OFFSET
                <int64>$offset
            LIMIT
                <int64>$limit
        """

        mediatypes = list(MediaItem.ALLOWED_MEDIA_TYPES)
        objs = await self.conn.query(
            query,
            user_id=user_id,
            path=config.features.photos_library_path,
            mediatypes=mediatypes,
            offset=offset,
            limit=limit,
        )
        return [_from_db(obj) for obj in objs]
