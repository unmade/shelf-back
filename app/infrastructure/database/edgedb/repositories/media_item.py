from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import edgedb

from app.app.photos.domain import MediaItem
from app.app.photos.domain.media_item import MediaItemCategory
from app.app.photos.repositories import IMediaItemRepository
from app.config import config
from app.toolkit import json_

if TYPE_CHECKING:
    from uuid import UUID

    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext

__all__ = ["MediaItemRepository"]

_ORIGIN_TO_INT = {
    MediaItemCategory.Origin.AUTO: 0,
    MediaItemCategory.Origin.USER: 1,
}

_INT_TO_ORIGIN = dict(zip(_ORIGIN_TO_INT.values(), _ORIGIN_TO_INT.keys(), strict=False))


def _dump_category(category: MediaItemCategory) -> str:
    return json_.dumps({
        "name": category.name,
        "origin": _ORIGIN_TO_INT[category.origin],
        "probability": category.probability,
    })


def _load_category(obj) -> MediaItemCategory:
    return MediaItemCategory(
        name=obj.name,
        origin=_INT_TO_ORIGIN[obj["@origin"]],
        probability=obj["@probability"],
    )


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

    async def add_category_batch(
        self, file_id: UUID, categories: Sequence[MediaItemCategory]
    ) -> None:
        query = """
            WITH
                categories := (
                    FOR category in {array_unpack(<array<json>>$categories)}
                    UNION (
                        INSERT FileCategory {
                            name := <str>category['name']
                        }
                        UNLESS CONFLICT on .name
                        ELSE FileCategory
                    )
                )
            UPDATE
                File
            FILTER
                .id = <uuid>$file_id
            SET {
                categories += (
                    FOR category in {array_unpack(<array<json>>$categories)}
                    UNION (
                        SELECT categories {
                            name,
                            @origin := <int16>category['origin'],
                            @probability := <int16>category['probability'],
                        }
                        FILTER
                            .name = <str>category['name']
                    )
                )
            }
        """

        try:
            await self.conn.query_required_single(
                query,
                file_id=file_id,
                categories=[_dump_category(category) for category in categories],
            )
        except edgedb.NoDataError as exc:
            raise MediaItem.NotFound() from exc

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
