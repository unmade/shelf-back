from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING, cast

from tortoise.exceptions import DoesNotExist, IntegrityError

from app.app.photos.domain import MediaItem
from app.app.photos.domain.media_item import (
    IMediaItemType,
    MediaItemCategory,
    MediaItemCategoryName,
)
from app.app.photos.repositories.media_item import CountResult
from app.config import config
from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from uuid import UUID

__all__ = ["MediaItemRepository"]

_ORIGIN_TO_INT = {
    MediaItemCategory.Origin.AUTO: 0,
    MediaItemCategory.Origin.USER: 1,
}

_INT_TO_ORIGIN = dict(zip(_ORIGIN_TO_INT.values(), _ORIGIN_TO_INT.keys(), strict=False))


def _from_db(obj: models.File) -> MediaItem:
    return MediaItem(
        file_id=obj.id,
        name=obj.name,
        size=obj.size,
        modified_at=obj.modified_at,
        deleted_at=obj.deleted_at,
        mediatype=cast(IMediaItemType, obj.mediatype.name),
    )


def _base_qs():
    """Base queryset filtered by allowed media types and photos library path."""
    return (
        models.File
        .filter(
            mediatype__name__in=list(MediaItem.ALLOWED_MEDIA_TYPES),
            path__istartswith=config.features.photos_library_path,
        )
        .select_related("mediatype")
    )


class MediaItemRepository:
    async def add_category_batch(
        self, file_id: UUID, categories: Sequence[MediaItemCategory]
    ) -> None:
        try:
            file_obj = await models.File.get(id=file_id)
        except DoesNotExist as exc:
            raise MediaItem.NotFound() from exc

        for category in categories:
            try:
                cat_obj = await models.FileCategory.create(name=category.name)
            except IntegrityError:
                cat_obj = await models.FileCategory.get(name=category.name)

            await models.FileFileCategoryThrough.create(
                file=file_obj,
                file_category=cat_obj,
                origin=_ORIGIN_TO_INT[category.origin],
                probability=category.probability,
            )

    async def count(self, user_id: UUID) -> CountResult:
        base = (
            models.File
            .filter(
                mediatype__name__in=list(MediaItem.ALLOWED_MEDIA_TYPES),
                path__istartswith=config.features.photos_library_path,
                namespace__owner_id=user_id,
            )
        )
        total = await base.filter(deleted_at__isnull=True).count()
        deleted = await base.filter(deleted_at__isnull=False).count()
        return CountResult(total=total, deleted=deleted)

    async def get_by_id_batch(self, file_ids: Sequence[UUID]) -> list[MediaItem]:
        objs = await (
            _base_qs()
            .filter(id__in=list(file_ids))
            .order_by("-modified_at")
        )
        return [_from_db(obj) for obj in objs]

    async def get_by_user_id(self, user_id: UUID, file_id: UUID) -> MediaItem:
        try:
            obj = await (
                models.File
                .filter(id=file_id, namespace__owner_id=user_id)
                .select_related("mediatype")
                .get()
            )
        except DoesNotExist as exc:
            raise MediaItem.NotFound() from exc
        return _from_db(obj)

    async def list_by_user_id(
        self,
        user_id: UUID,
        *,
        only_favourites: bool = False,
        offset: int,
        limit: int = 25,
    ) -> list[MediaItem]:
        qs = (
            _base_qs()
            .filter(
                namespace__owner_id=user_id,
                deleted_at__isnull=True,
            )
        )
        if only_favourites:
            bookmarked_ids = await (
                models.Bookmark
                .filter(user_id=user_id)
                .values_list("file_id", flat=True)
            )
            qs = qs.filter(id__in=list(bookmarked_ids))

        objs = await qs.order_by("-modified_at").offset(offset).limit(limit)
        return [_from_db(obj) for obj in objs]

    async def list_categories(self, file_id: UUID) -> list[MediaItemCategory]:
        if not await models.File.filter(id=file_id).exists():
            raise MediaItem.NotFound()

        through_objs = await (
            models.FileFileCategoryThrough
            .filter(file_id=file_id)
            .select_related("file_category")
        )
        return [
            MediaItemCategory(
                name=MediaItemCategoryName(obj.file_category.name),
                origin=_INT_TO_ORIGIN[obj.origin],
                probability=obj.probability,
            )
            for obj in through_objs
        ]

    async def list_deleted(
        self, user_id: UUID, *, offset: int, limit: int = 25
    ) -> list[MediaItem]:
        objs = await (
            _base_qs()
            .filter(
                namespace__owner_id=user_id,
                deleted_at__isnull=False,
            )
            .order_by("-deleted_at")
            .offset(offset)
            .limit(limit)
        )
        return [_from_db(obj) for obj in objs]

    async def set_categories(
        self, file_id: UUID, categories: Sequence[MediaItemCategory]
    ) -> None:
        if not await models.File.filter(id=file_id).exists():
            raise MediaItem.NotFound()

        # Clear existing categories
        await models.FileFileCategoryThrough.filter(file_id=file_id).delete()

        for category in categories:
            try:
                cat_obj = await models.FileCategory.create(name=category.name)
            except IntegrityError:
                cat_obj = await models.FileCategory.get(name=category.name)

            await models.FileFileCategoryThrough.create(
                file_id=file_id,
                file_category=cat_obj,
                origin=_ORIGIN_TO_INT[category.origin],
                probability=category.probability,
            )

    async def set_deleted_at_batch(
        self, user_id: UUID, file_ids: Sequence[UUID], deleted_at: datetime | None
    ) -> list[MediaItem]:
        matching_ids: list[UUID] = await (  # type: ignore[assignment]
            models.File
            .filter(
                id__in=list(file_ids),
                mediatype__name__in=list(MediaItem.ALLOWED_MEDIA_TYPES),
                path__istartswith=config.features.photos_library_path,
                namespace__owner_id=user_id,
            )
            .values_list("id", flat=True)
        )
        if matching_ids:
            await models.File.filter(id__in=matching_ids).update(deleted_at=deleted_at)

        objs = await (
            _base_qs()
            .filter(
                id__in=list(file_ids),
                namespace__owner_id=user_id,
            )
            .order_by("-modified_at")
        )
        return [_from_db(obj) for obj in objs]
