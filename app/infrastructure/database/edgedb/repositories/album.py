from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID

import edgedb

from app.app.photos.domain import Album, MediaItem
from app.app.photos.repositories import IAlbumRepository

if TYPE_CHECKING:

    from app.infrastructure.database.edgedb.typedefs import EdgeDBAnyConn, EdgeDBContext

__all__ = ["AlbumRepository"]


def _from_db(obj) -> Album:
    cover = Album.Cover(file_id=obj.cover.id) if obj.cover else None
    return Album(
        id=obj.id,
        owner_id=obj.owner.id,
        title=obj.title,
        slug=obj.slug,
        created_at=obj.created_at,
        items_count=obj.items_count,
        cover=cover,
    )


def _media_item_from_db(obj) -> MediaItem:
    return MediaItem(
        file_id=obj.id,
        name=obj.name,
        size=obj.size,
        modified_at=obj.modified_at,
        deleted_at=obj.deleted_at,
        mediatype=obj.mediatype.name
    )


class AlbumRepository(IAlbumRepository):
    def __init__(self, db_context: EdgeDBContext):
        self.db_context = db_context

    @property
    def conn(self) -> EdgeDBAnyConn:
        return self.db_context.get()

    async def add_items(
        self, owner_id: UUID, slug: str, file_ids: list[UUID]
    ) -> Album:
        query = """
            WITH
                owner := (SELECT User FILTER .id = <uuid>$owner_id),
                album := (
                    SELECT
                        Album
                    FILTER
                        .owner = owner
                        AND
                        .slug = <str>$slug
                ),
            SELECT (
                UPDATE
                    album
                SET {
                    items += (
                        SELECT
                            File
                        FILTER
                            .id IN {array_unpack(<array<uuid>>$file_ids)}
                    ),
                    items_count := .items_count + <int32>len(<array<uuid>>$file_ids)
                }
            ) { title, slug, owner, cover, items_count, created_at }
        """

        try:
            obj = await self.conn.query_required_single(
                query, owner_id=owner_id, slug=slug, file_ids=file_ids
            )
        except edgedb.NoDataError as exc:
            raise Album.NotFound() from exc

        return _from_db(obj)

    async def count_by_slug_pattern(self, owner_id: UUID, pattern: str) -> int:
        query = """
            WITH
                owner := (SELECT User FILTER .id = <uuid>$owner_id),
            SELECT count(
                Album
                FILTER
                    .owner = owner
                    AND
                    re_test(<str>$pattern, .slug)
            )
        """
        return cast(
            int,
            await self.conn.query_required_single(
                query, owner_id=owner_id, pattern=pattern
            )
        )

    async def exists_with_slug(self, owner_id: UUID, slug: str) -> bool:
        query = """
            SELECT EXISTS (
                SELECT
                    Album
                FILTER
                    .owner.id = <uuid>$owner_id
                    AND
                    .slug = <str>$slug
            )
        """

        exists = await self.conn.query_required_single(
            query, owner_id=owner_id, slug=slug
        )
        return cast(bool, exists)

    async def get_by_slug(self, owner_id: UUID, slug: str) -> Album:
        query = """
            WITH
                owner := (SELECT User FILTER .id = <uuid>$owner_id),
            SELECT
                Album { title, slug, owner, cover, items_count, created_at }
            FILTER
                .owner = owner
                AND
                .slug = <str>$slug
            LIMIT 1
        """

        try:
            obj = await self.conn.query_required_single(
                query, owner_id=owner_id, slug=slug
            )
        except edgedb.NoDataError as exc:
            raise Album.NotFound() from exc

        return _from_db(obj)

    async def list_by_owner_id(
        self, owner_id: UUID, *, offset: int, limit: int = 25
    ) -> list[Album]:
        query = """
            SELECT
                Album { title, slug, owner, cover, items_count, created_at }
            FILTER
                .owner.id = <uuid>$owner_id
            ORDER BY
                .title
            OFFSET
                <int64>$offset
            LIMIT
                <int64>$limit
        """

        objs = await self.conn.query(
            query, owner_id=owner_id, offset=offset, limit=limit
        )

        return [_from_db(obj) for obj in objs]

    async def list_items(
        self,
        user_id: UUID,
        album_slug: str,
        *,
        offset: int,
        limit: int = 25,
    ) -> list[MediaItem]:
        query = """
            WITH
                owner := (SELECT User FILTER .id = <uuid>$user_id),
            SELECT
                Album {
                    items := (
                        SELECT
                            .items {
                                id, name, size, modified_at, deleted_at,
                                mediatype: { name }
                            }
                        ORDER BY
                            .modified_at DESC
                        OFFSET
                            <int64>$offset
                        LIMIT
                            <int64>$limit
                    )
                }
            FILTER
                .owner = owner
                AND
                .slug = <str>$slug
            LIMIT 1
        """

        obj = await self.conn.query_required_single(
            query, user_id=user_id, slug=album_slug, offset=offset, limit=limit
        )
        return [_media_item_from_db(item) for item in obj.items]

    async def remove_items(
        self, owner_id: UUID, slug: str, file_ids: list[UUID]
    ) -> Album:
        query = """
            WITH
                owner := (SELECT User FILTER .id = <uuid>$owner_id),
                album := (
                    SELECT
                        Album
                    FILTER
                        .owner = owner
                        AND
                        .slug = <str>$slug
                ),
            SELECT (
                UPDATE album
                SET {
                    items -= (
                        SELECT
                            File
                        FILTER
                            .id IN {array_unpack(<array<uuid>>$file_ids)}
                    ),
                    items_count := .items_count - <int32>len(<array<uuid>>$file_ids)
                }
            ) { title, slug, owner, cover, items_count, created_at }
        """

        try:
            obj = await self.conn.query_required_single(
                query, owner_id=owner_id, slug=slug, file_ids=file_ids
            )
        except edgedb.NoDataError as exc:
            raise Album.NotFound() from exc

        return _from_db(obj)

    async def save(self, entity: Album) -> Album:
        query = """
            WITH
                owner := (SELECT User FILTER .id = <uuid>$owner_id),
            INSERT Album {
                title := <str>$title,
                slug := <str>$slug,
                owner := owner,
                items_count := <int32>$items_count,
                created_at := <datetime>$created_at,
            }
        """

        obj = await self.conn.query_required_single(
            query,
            title=entity.title,
            slug=entity.slug,
            owner_id=entity.owner_id,
            items_count=entity.items_count,
            created_at=entity.created_at,
        )

        return entity.model_copy(update={"id": obj.id})

    async def set_cover(self, owner_id: UUID, slug: str, file_id: UUID | None) -> Album:
        query = """
            WITH
                owner := (SELECT User FILTER .id = <uuid>$owner_id),
                album := (
                    SELECT
                        Album
                    FILTER
                        .owner = owner
                        AND
                        .slug = <str>$slug
                ),
                file_id := <OPTIONAL uuid>$file_id,
                file := (
                    SELECT (SELECT File FILTER .id = file_id) if exists file_id else {}
                ),
            SELECT (
                UPDATE album SET {
                    cover := file
                }
            ) { title, slug, owner, cover, items_count, created_at }
        """
        try:
            obj = await self.conn.query_required_single(
                query, owner_id=owner_id, slug=slug, file_id=file_id
            )
        except edgedb.NoDataError as exc:
            raise Album.NotFound() from exc

        return _from_db(obj)
