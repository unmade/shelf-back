from __future__ import annotations

from typing import TYPE_CHECKING, Any, Unpack, cast

from pypika_tortoise.enums import Order
from pypika_tortoise.queries import Table
from tortoise import connections
from tortoise.exceptions import DoesNotExist
from tortoise.fields.relational import ManyToManyFieldInstance

from app.app.photos.domain import Album, MediaItem
from app.app.photos.repositories import IAlbumRepository
from app.app.photos.repositories.album import AlbumUpdate
from app.infrastructure.database.tortoise import models
from app.infrastructure.database.tortoise.repositories.media_item import (
    _from_db as _media_item_from_db,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

__all__ = ["AlbumRepository"]


def _from_db(obj: models.Album) -> Album:
    cover = Album.Cover(media_item_id=obj.cover_id) if obj.cover_id else None  # type: ignore[attr-defined]
    return Album(
        id=obj.id,
        owner_id=obj.owner_id,  # type: ignore[attr-defined]
        title=obj.title,
        slug=obj.slug,
        created_at=obj.created_at,
        items_count=obj.items_count,
        cover=cover,
    )


class AlbumRepository(IAlbumRepository):
    async def add_items(
        self, owner_id: UUID, slug: str, media_item_ids: list[UUID]
    ) -> Album:
        try:
            obj = await models.Album.get(owner_id=owner_id, slug=slug)
        except DoesNotExist as exc:
            raise Album.NotFound() from exc

        items = await models.MediaItem.filter(id__in=media_item_ids)
        await obj.items.add(*items)
        obj.items_count += len(media_item_ids)
        await obj.save(update_fields=["items_count"])
        return _from_db(obj)

    async def count_by_slug_pattern(self, owner_id: UUID, pattern: str) -> int:
        return await (
            models.Album
            .filter(
                owner_id=owner_id,
                slug__iposix_regex=pattern,
            )
            .count()
        )

    async def delete(self, owner_id: UUID, slug: str) -> Album:
        try:
            obj = await models.Album.get(owner_id=owner_id, slug=slug)
        except DoesNotExist as exc:
            raise Album.NotFound() from exc

        album = _from_db(obj)
        await obj.delete()
        return album

    async def exists_with_slug(self, owner_id: UUID, slug: str) -> bool:
        return await models.Album.filter(owner_id=owner_id, slug=slug).exists()

    async def get_by_slug(self, owner_id: UUID, slug: str) -> Album:
        try:
            obj = await models.Album.get(owner_id=owner_id, slug=slug)
        except DoesNotExist as exc:
            raise Album.NotFound() from exc
        return _from_db(obj)

    async def list_by_owner_id(
        self, owner_id: UUID, *, offset: int, limit: int = 25
    ) -> list[Album]:
        objs = await (
            models.Album
            .filter(owner_id=owner_id)
            .order_by("title")
            .offset(offset)
            .limit(limit)
        )
        return [_from_db(obj) for obj in objs]

    async def list_cover_candidates(
        self, album_ids: Sequence[UUID]
    ) -> list[tuple[UUID, UUID]]:
        if not album_ids:
            return []

        # normally that should be a simple ORM query with a `Subquery`:
        #
        # >>> items = models.MediaItem.filter(
        # >>>     album=OuterRef('pk'),   # Tortoise ORM does not support `OuterRef`.
        # >>>     deleted_at__isnull=True
        # >>> ).order_by('-modified_at')
        # >>>
        # >>> await (
        # >>>     models.Album
        # >>>     .filter(id__in=album_ids)
        # >>>     .annotate(media_item_id=Subquery(items.limit(1).values('id')))
        # >>>     .values_list('id', 'media_item_id')
        # >>> )

        connection = connections.get("default")
        items_field = cast(
            ManyToManyFieldInstance[Any],
            models.Album._meta.fields_map["items"],
        )
        albums = Table(models.Album._meta.db_table).as_("album")
        album_items = Table(items_field.through).as_("album_items")
        media_items = Table(models.MediaItem._meta.db_table).as_("media_items")

        candidate_media_item_id = (
            connection.query_class
            .from_(album_items)
            .join(media_items)
            .on(album_items[items_field.forward_key] == media_items.id)
            .select(media_items.id)
            .where(album_items[items_field.backward_key] == albums.id)
            .where(media_items.deleted_at.isnull())
            .orderby(media_items.modified_at, order=Order.desc)
            .orderby(media_items.id, order=Order.asc)
            .limit(1)
            .as_("media_item_id")
        )

        query = (
            connection.query_class
            .from_(albums)
            .select(albums.id.as_("album_id"), candidate_media_item_id)
            .where(albums.id.isin(list(album_ids)))
            .orderby(albums.id)
        )
        sql, params = query.get_parameterized_sql()
        rows = await connection.execute_query_dict(sql, params)

        return [
            (row["album_id"], row["media_item_id"])
            for row in rows
            if row["media_item_id"] is not None
        ]

    async def list_ids_by_cover_ids(
        self, owner_id: UUID, cover_ids: Sequence[UUID]
    ) -> list[UUID]:
        target_cover_ids = list(dict.fromkeys(cover_ids))
        if not target_cover_ids:
            return []

        album_ids: list[UUID] = await (  # type: ignore[assignment]
            models.Album
            .filter(owner_id=owner_id, cover_id__in=target_cover_ids)
            .values_list("id", flat=True)
        )
        return album_ids

    async def list_items(
        self,
        owner_id: UUID,
        slug: str,
        *,
        offset: int,
        limit: int = 25,
    ) -> list[MediaItem]:
        items = await (
            models.MediaItem
            .filter(
                albums__owner_id=owner_id,
                albums__slug=slug,
                deleted_at__isnull=True,
            )
            .select_related("blob")
            .prefetch_related("blob__metadata")
            .order_by("-modified_at")
            .offset(offset)
            .limit(limit)
        )
        return [_media_item_from_db(item) for item in items]

    async def remove_items(
        self, owner_id: UUID, slug: str, media_item_ids: list[UUID]
    ) -> Album:
        try:
            obj = await models.Album.get(owner_id=owner_id, slug=slug)
        except DoesNotExist as exc:
            raise Album.NotFound() from exc

        items = await models.MediaItem.filter(id__in=media_item_ids)
        await obj.items.remove(*items)
        obj.items_count -= len(media_item_ids)
        await obj.save(update_fields=["items_count"])
        return _from_db(obj)

    async def save(self, entity: Album) -> Album:
        obj = await models.Album.create(
            title=entity.title,
            slug=entity.slug,
            owner_id=entity.owner_id,
            items_count=entity.items_count,
            created_at=entity.created_at,
        )
        return entity.model_copy(update={"id": obj.id})

    async def set_cover(
        self, owner_id: UUID, slug: str, media_item_id: UUID | None
    ) -> Album:
        try:
            obj = await models.Album.get(owner_id=owner_id, slug=slug)
        except DoesNotExist as exc:
            raise Album.NotFound() from exc

        obj.cover_id = media_item_id
        await obj.save(update_fields=["cover_id"])
        return _from_db(obj)

    async def set_cover_batch(
        self, covers: Sequence[tuple[UUID, UUID | None]]
    ) -> None:
        if not covers:
            return

        cover_by_album_id = dict(covers)
        albums = await models.Album.filter(id__in=list(cover_by_album_id))
        if not albums:
            return

        for album in albums:
            album.cover_id = cover_by_album_id[album.id]

        await models.Album.bulk_update(albums, fields=["cover_id"])

    async def update(
        self, entity: Album, **fields: Unpack[AlbumUpdate]
    ) -> Album:
        try:
            obj = await models.Album.get(
                owner_id=entity.owner_id, slug=entity.slug
            )
        except DoesNotExist as exc:
            raise Album.NotFound() from exc

        for key, value in fields.items():
            setattr(obj, key, value)
        await obj.save(update_fields=list(fields.keys()))
        return _from_db(obj)
