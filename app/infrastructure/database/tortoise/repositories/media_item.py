from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from tortoise.exceptions import DoesNotExist

from app.app.blobs.domain import BlobMetadata
from app.app.photos.domain import MediaItem
from app.app.photos.domain.media_item import (
    MediaItemCategory,
    MediaItemCategoryName,
)
from app.app.photos.repositories.media_item import CountResult
from app.infrastructure.database.tortoise import models
from app.toolkit import timezone

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from uuid import UUID

__all__ = ["MediaItemRepository"]

_ORIGIN_TO_INT = {
    MediaItemCategory.Origin.AUTO: 0,
    MediaItemCategory.Origin.USER: 1,
}

_INT_TO_ORIGIN = dict(zip(_ORIGIN_TO_INT.values(), _ORIGIN_TO_INT.keys(), strict=False))


def _from_db(obj: models.MediaItem) -> MediaItem:
    blob = obj.blob
    metadata: BlobMetadata | None = None
    if raw_metadata := blob.metadata:  # type: ignore[attr-defined]
        metadata = BlobMetadata(
            blob_id=raw_metadata.blob_id,
            data=raw_metadata.data,
        )

    taken_at = None
    if metadata is not None and metadata.data.dt_original is not None:
        taken_at = timezone.fromtimestamp(metadata.data.dt_original)

    return MediaItem(
        id=obj.id,
        owner_id=obj.owner_id,  # type: ignore[attr-defined]
        blob_id=obj.blob_id,  # type: ignore[attr-defined]
        name=obj.name,
        media_type=blob.media_type,
        size=blob.size,
        chash=blob.chash,
        taken_at=taken_at,
        created_at=obj.created_at,
        modified_at=obj.modified_at,
        deleted_at=obj.deleted_at,
    )


def _base_qs():
    """Base queryset with Blob and BlobMetadata JOINs."""
    return (
        models.MediaItem
        .all()
        .select_related("blob")
        .prefetch_related("blob__metadata")
    )


async def _get_or_create_categories(
    names: Iterable[str],
) -> dict[str, models.FileCategory]:
    unique_names = list(set(names))
    categories = await models.FileCategory.filter(name__in=unique_names)
    by_name = {cat.name: cat for cat in categories}

    missing_names = [name for name in unique_names if name not in by_name]
    if missing_names:
        to_create = [models.FileCategory(name=name) for name in missing_names]
        await models.FileCategory.bulk_create(to_create)
        by_name.update({category.name: category for category in to_create})

    return by_name


class MediaItemRepository:
    async def add_category_batch(
        self, media_item_id: UUID, categories: Sequence[MediaItemCategory]
    ) -> None:
        if not await models.MediaItem.filter(id=media_item_id).exists():
            raise MediaItem.NotFound()

        if not categories:
            return

        cat_by_name = await _get_or_create_categories(c.name for c in categories)

        existing_through = await (
            models.MediaItemCategoryThrough
            .filter(media_item_id=media_item_id)
        )
        existing_by_cat_id = {
            obj.file_category_id: obj  # type: ignore[attr-defined]
            for obj in existing_through
        }

        to_create = []
        to_update = []
        for category in categories:
            cat_id = cat_by_name[category.name].id
            origin = _ORIGIN_TO_INT[category.origin]
            if cat_id in existing_by_cat_id:
                obj = existing_by_cat_id[cat_id]
                obj.origin = origin
                obj.probability = category.probability
                to_update.append(obj)
            else:
                to_create.append(
                    models.MediaItemCategoryThrough(
                        media_item_id=media_item_id,
                        file_category_id=cat_id,
                        origin=origin,
                        probability=category.probability,
                    )
                )

        if to_update:
            await models.MediaItemCategoryThrough.bulk_update(
                to_update, fields=["origin", "probability"],
            )
        if to_create:
            await models.MediaItemCategoryThrough.bulk_create(to_create)

    async def count(self, owner_id: UUID) -> CountResult:
        base = models.MediaItem.filter(owner_id=owner_id)
        total = await base.filter(deleted_at__isnull=True).count()
        deleted = await base.filter(deleted_at__isnull=False).count()
        return CountResult(total=total, deleted=deleted)

    async def delete_batch(self, ids: Sequence[UUID]) -> None:
        await models.MediaItem.filter(id__in=list(ids)).delete()

    async def get_by_id(self, media_item_id: UUID) -> MediaItem:
        try:
            obj = await _base_qs().get(id=media_item_id)
        except DoesNotExist as exc:
            raise MediaItem.NotFound() from exc
        return _from_db(obj)

    async def get_by_id_batch(
        self, media_item_ids: Sequence[UUID]
    ) -> list[MediaItem]:
        objs = await (
            _base_qs()
            .filter(id__in=list(media_item_ids))
            .order_by("-modified_at")
        )
        return [_from_db(obj) for obj in objs]

    async def get_for_owner(
        self, owner_id: UUID, media_item_id: UUID
    ) -> MediaItem:
        try:
            obj = await _base_qs().get(id=media_item_id, owner_id=owner_id)
        except DoesNotExist as exc:
            raise MediaItem.NotFound() from exc
        return _from_db(obj)

    async def list_by_owner(
        self,
        owner_id: UUID,
        *,
        only_favourites: bool = False,
        offset: int,
        limit: int = 25,
    ) -> list[MediaItem]:
        qs = (
            _base_qs()
            .filter(owner_id=owner_id, deleted_at__isnull=True)
        )
        if only_favourites:
            favourite_ids: list[UUID] = await (  # type: ignore[assignment]
                models.MediaItemBookmark
                .filter(user_id=owner_id)
                .values_list("media_item_id", flat=True)
            )
            qs = qs.filter(id__in=list(favourite_ids))

        objs = await qs.order_by("-modified_at").offset(offset).limit(limit)
        return [_from_db(obj) for obj in objs]

    async def list_categories(
        self, media_item_id: UUID
    ) -> list[MediaItemCategory]:
        if not await models.MediaItem.filter(id=media_item_id).exists():
            raise MediaItem.NotFound()

        through_objs = await (
            models.MediaItemCategoryThrough
            .filter(media_item_id=media_item_id)
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
        self, owner_id: UUID, *, offset: int, limit: int = 25
    ) -> list[MediaItem]:
        objs = await (
            _base_qs()
            .filter(owner_id=owner_id, deleted_at__isnull=False)
            .order_by("-deleted_at")
            .offset(offset)
            .limit(limit)
        )
        return [_from_db(obj) for obj in objs]

    async def save(self, item: MediaItem) -> MediaItem:
        obj = await models.MediaItem.create(
            owner_id=item.owner_id,
            blob_id=item.blob_id,
            name=item.name,
            created_at=item.created_at,
            modified_at=item.modified_at,
            deleted_at=item.deleted_at,
        )
        return item.model_copy(update={"id": obj.id})

    async def set_categories(
        self, media_item_id: UUID, categories: Sequence[MediaItemCategory]
    ) -> None:
        if not await models.MediaItem.filter(id=media_item_id).exists():
            raise MediaItem.NotFound()

        await models.MediaItemCategoryThrough.filter(
            media_item_id=media_item_id
        ).delete()

        if not categories:
            return

        cat_by_name = await _get_or_create_categories(c.name for c in categories)
        through_objs = [
            models.MediaItemCategoryThrough(
                media_item_id=media_item_id,
                file_category_id=cat_by_name[category.name].id,
                origin=_ORIGIN_TO_INT[category.origin],
                probability=category.probability,
            )
            for category in categories
        ]
        await models.MediaItemCategoryThrough.bulk_create(through_objs)

    async def set_deleted_at_batch(
        self, owner_id: UUID, ids: Sequence[UUID], deleted_at: datetime | None
    ) -> list[MediaItem]:
        matching_ids: list[UUID] = await (  # type: ignore[assignment]
            models.MediaItem
            .filter(id__in=list(ids), owner_id=owner_id)
            .values_list("id", flat=True)
        )
        await models.MediaItem.filter(id__in=matching_ids).update(
            deleted_at=deleted_at
        )

        objs = await (
            _base_qs()
            .filter(id__in=list(ids), owner_id=owner_id)
            .order_by("-modified_at")
        )
        return [_from_db(obj) for obj in objs]
