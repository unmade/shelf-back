from __future__ import annotations

from typing import TYPE_CHECKING, Unpack, cast

from tortoise.exceptions import DoesNotExist

from app.app.photos.domain import Album, MediaItem
from app.app.photos.domain.media_item import IMediaItemType
from app.app.photos.repositories import IAlbumRepository
from app.app.photos.repositories.album import AlbumUpdate
from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from uuid import UUID

__all__ = ["AlbumRepository"]


def _from_db(obj: models.Album) -> Album:
    cover = Album.Cover(file_id=obj.cover_id) if obj.cover_id else None  # type: ignore[attr-defined]
    return Album(
        id=obj.id,
        owner_id=obj.owner_id,  # type: ignore[attr-defined]
        title=obj.title,
        slug=obj.slug,
        created_at=obj.created_at,
        items_count=obj.items_count,
        cover=cover,
    )


def _media_item_from_db(obj: models.File) -> MediaItem:
    return MediaItem(
        file_id=obj.id,
        name=obj.name,
        size=obj.size,
        modified_at=obj.modified_at,
        deleted_at=obj.deleted_at,
        mediatype=cast(IMediaItemType, obj.mediatype.name),
    )


class AlbumRepository(IAlbumRepository):
    async def add_items(
        self, owner_id: UUID, slug: str, file_ids: list[UUID]
    ) -> Album:
        try:
            obj = await models.Album.get(owner_id=owner_id, slug=slug)
        except DoesNotExist as exc:
            raise Album.NotFound() from exc

        files = await models.File.filter(id__in=file_ids)
        await obj.items.add(*files)
        obj.items_count += len(file_ids)
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

    async def list_items(
        self,
        user_id: UUID,
        slug: str,
        *,
        offset: int,
        limit: int = 25,
    ) -> list[MediaItem]:
        items = await (
            models.File
            .filter(albums__owner_id=user_id, albums__slug=slug)
            .select_related("mediatype")
            .order_by("-modified_at")
            .offset(offset)
            .limit(limit)
        )
        return [_media_item_from_db(item) for item in items]

    async def remove_items(
        self, owner_id: UUID, slug: str, file_ids: list[UUID]
    ) -> Album:
        try:
            obj = await models.Album.get(owner_id=owner_id, slug=slug)
        except DoesNotExist as exc:
            raise Album.NotFound() from exc

        files = await models.File.filter(id__in=file_ids)
        await obj.items.remove(*files)
        obj.items_count -= len(file_ids)
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
        self, owner_id: UUID, slug: str, file_id: UUID | None
    ) -> Album:
        try:
            obj = await models.Album.get(owner_id=owner_id, slug=slug)
        except DoesNotExist as exc:
            raise Album.NotFound() from exc

        obj.cover_id = file_id
        await obj.save(update_fields=["cover_id"])
        return _from_db(obj)

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
