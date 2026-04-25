from __future__ import annotations

import operator
import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.photos.domain import MediaItem
from app.app.photos.domain.media_item import MediaItemCategoryName
from app.infrastructure.database.tortoise import models
from app.toolkit import timezone
from app.toolkit.mediatypes import MediaType
from app.toolkit.metadata import Exif

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.photos.domain.media_item import MediaItemCategory
    from app.app.users.domain import User
    from app.infrastructure.database.tortoise.repositories import MediaItemRepository
    from tests.infrastructure.database.tortoise.conftest import (
        BlobMetadataFactory,
        MediaItemFactory,
    )

pytestmark = [pytest.mark.anyio, pytest.mark.database]


_ORIGIN_TO_INT = {
    MediaItem.Category.Origin.AUTO: 0,
    MediaItem.Category.Origin.USER: 1,
}

_INT_TO_ORIGIN = dict(zip(_ORIGIN_TO_INT.values(), _ORIGIN_TO_INT.keys(), strict=False))


async def _add_category(media_item_id: UUID, category: MediaItemCategory) -> None:
    cat_obj, _ = await models.MediaItemCategory.get_or_create(name=category.name)
    await models.MediaItemCategoryThrough.create(
        media_item_id=media_item_id,
        media_item_category=cat_obj,
        origin=_ORIGIN_TO_INT[category.origin],
        probability=category.probability,
    )


async def _list_categories_by_id(media_item_id: UUID) -> list[MediaItemCategory]:
    through_objs = await (
        models.MediaItemCategoryThrough
        .filter(media_item_id=media_item_id)
        .select_related("media_item_category")
        .order_by("probability")
    )
    return [
        MediaItem.Category(
            name=MediaItemCategoryName(obj.media_item_category.name),
            origin=_INT_TO_ORIGIN[obj.origin],
            probability=obj.probability,
        )
        for obj in through_objs
    ]


class TestAddCategoryBatch:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        item = await media_item_factory(user.id)
        categories = [
            MediaItem.Category(
                name=MediaItem.Category.Name.ANIMALS,
                origin=MediaItem.Category.Origin.AUTO,
                probability=78,
            ),
            MediaItem.Category(
                name=MediaItem.Category.Name.PETS,
                origin=MediaItem.Category.Origin.AUTO,
                probability=84,
            ),
        ]
        # WHEN
        await media_item_repo.add_category_batch(item.id, categories)
        # THEN
        result = await _list_categories_by_id(item.id)
        assert result == categories

    async def test_adds_new_and_updates_existing(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        item = await media_item_factory(user.id)
        existing_categories = [
            MediaItem.Category(
                name=MediaItem.Category.Name.LANDSCAPES,
                origin=MediaItem.Category.Origin.AUTO,
                probability=33,
            ),
            MediaItem.Category(
                name=MediaItem.Category.Name.ANIMALS,
                origin=MediaItem.Category.Origin.AUTO,
                probability=66,
            ),
        ]
        await media_item_repo.add_category_batch(item.id, existing_categories)

        new_categories = [
            MediaItem.Category(
                name=MediaItem.Category.Name.ANIMALS,
                origin=MediaItem.Category.Origin.AUTO,
                probability=78,
            ),
            MediaItem.Category(
                name=MediaItem.Category.Name.PETS,
                origin=MediaItem.Category.Origin.AUTO,
                probability=84,
            ),
        ]
        # WHEN
        await media_item_repo.add_category_batch(item.id, new_categories)
        # THEN: LANDSCAPES unchanged, ANIMALS updated, PETS added
        result = await _list_categories_by_id(item.id)
        assert len(result) == 3
        assert result == [
            existing_categories[0],
            new_categories[0],
            new_categories[1],
        ]

    async def test_updates_all_existing(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        item = await media_item_factory(user.id)
        categories = [
            MediaItem.Category(
                name=MediaItem.Category.Name.ANIMALS,
                origin=MediaItem.Category.Origin.AUTO,
                probability=50,
            ),
        ]
        await media_item_repo.add_category_batch(item.id, categories)

        updated_categories = [
            MediaItem.Category(
                name=MediaItem.Category.Name.ANIMALS,
                origin=MediaItem.Category.Origin.AUTO,
                probability=90,
            ),
        ]
        # WHEN
        await media_item_repo.add_category_batch(item.id, updated_categories)
        # THEN
        result = await _list_categories_by_id(item.id)
        assert result == updated_categories

    async def test_when_media_item_does_not_exist(
        self,
        media_item_repo: MediaItemRepository,
    ):
        # GIVEN
        media_item_id = uuid.uuid7()
        # WHEN / THEN
        with pytest.raises(MediaItem.NotFound):
            await media_item_repo.add_category_batch(media_item_id, categories=[])

    async def test_with_empty_categories(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        item = await media_item_factory(user.id)
        categories = [
            MediaItem.Category(
                name=MediaItem.Category.Name.ANIMALS,
                origin=MediaItem.Category.Origin.USER,
                probability=90,
            ),
        ]
        await _add_category(item.id, categories[0])
        # WHEN
        await media_item_repo.add_category_batch(item.id, categories=[])
        # THEN
        assert await _list_categories_by_id(item.id) == categories


class TestCount:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        await media_item_factory(user.id),
        await media_item_factory(user.id),
        await media_item_factory(user.id, deleted_at=timezone.now()),
        # WHEN
        result = await media_item_repo.count(user.id)
        # THEN
        assert result.total == 2
        assert result.deleted == 1


class TestDeleteBatch:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        items = [
            await media_item_factory(user.id),
            await media_item_factory(user.id),
            await media_item_factory(user.id),
        ]
        ids = [item.id for item in items[:2]]
        # WHEN
        await media_item_repo.delete_batch(ids)
        # THEN
        assert await models.MediaItem.filter(id__in=ids).count() == 0
        assert await models.MediaItem.filter(id=items[-1].id).exists() is True


class TestGetByID:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        media_item = await media_item_factory(user.id)
        # WHEN
        result = await media_item_repo.get_by_id(media_item.id)
        # THEN
        assert result == media_item

    async def test_when_media_item_does_not_exist(
        self, media_item_repo: MediaItemRepository,
    ):
        # GIVEN
        media_item_id = uuid.uuid7()
        # WHEN / THEN
        with pytest.raises(MediaItem.NotFound):
            await media_item_repo.get_by_id(media_item_id)


class TestGetByIDBatch:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        items = [
            await media_item_factory(user.id),
            await media_item_factory(user.id),
            await media_item_factory(user.id),
        ]
        ids = [item.id for item in items[:2]]
        # WHEN
        result = await media_item_repo.get_by_id_batch(ids)
        # THEN
        assert result == list(reversed(items[:2]))


class TestGetByUserID:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        media_item = await media_item_factory(user.id)
        # WHEN
        result = await media_item_repo.get_for_owner(user.id, media_item.id)
        # THEN
        assert result == media_item

    async def test_when_media_item_does_not_exist(
        self, media_item_repo: MediaItemRepository, user: User,
    ):
        media_item_id = uuid.uuid7()
        with pytest.raises(MediaItem.NotFound):
            await media_item_repo.get_for_owner(user.id, media_item_id)


class TestListByOwner:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        blob_metadata_factory: BlobMetadataFactory,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        await media_item_factory(user.id, deleted_at=timezone.now()),
        items = [
            await media_item_factory(user.id, "im.gif", media_type=MediaType.IMAGE_GIF),
            await media_item_factory(user.id, "im.png", media_type=MediaType.IMAGE_PNG),
        ]
        items[0].taken_at = timezone.now()
        await blob_metadata_factory(
            items[0].blob_id,
            Exif(dt_original=items[0].taken_at.timestamp()),
        )
        # WHEN
        result = await media_item_repo.list_by_owner(user.id, offset=0)
        # THEN
        assert result == [
            items[1],
            items[0],
        ]

    async def test_only_favourites(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        items = [
            await media_item_factory(
                user.id, "im.jpg", media_type=MediaType.IMAGE_JPEG
            ),
            await media_item_factory(user.id, "im.png", media_type=MediaType.IMAGE_PNG),
            await media_item_factory(
                user.id, "i.heic", media_type=MediaType.IMAGE_HEIC
            ),
        ]
        await models.MediaItemFavourite.create(
            user_id=user.id, media_item_id=items[0].id
        )
        await models.MediaItemFavourite.create(
            user_id=user.id, media_item_id=items[-1].id
        )
        # WHEN
        result = await media_item_repo.list_by_owner(
            user.id, only_favourites=True, offset=0
        )
        # THEN
        assert result == sorted(
            [items[0], items[-1]],
            key=operator.attrgetter("modified_at"),
            reverse=True,
        )

    async def test_only_favourites_when_its_empty(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        await media_item_factory(user.id, "im.jpg", media_type=MediaType.IMAGE_JPEG),
        await media_item_factory(user.id, "im.png", media_type=MediaType.IMAGE_PNG),
        # WHEN
        result = await media_item_repo.list_by_owner(
            user.id, only_favourites=True, offset=0
        )
        # THEN
        assert result == []


class TestListCategories:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        item = await media_item_factory(user.id)
        categories = [
            MediaItem.Category(
                name=MediaItem.Category.Name.ANIMALS,
                origin=MediaItem.Category.Origin.USER,
                probability=100,
            ),
            MediaItem.Category(
                name=MediaItem.Category.Name.PETS,
                origin=MediaItem.Category.Origin.USER,
                probability=100,
            ),
        ]
        await _add_category(item.id, categories[0])
        await _add_category(item.id, categories[1])
        # WHEN
        result = await media_item_repo.list_categories(item.id)
        # THEN
        assert result == categories

    async def test_when_media_item_does_not_exist(
        self, media_item_repo: MediaItemRepository,
    ):
        media_item_id = uuid.uuid7()
        with pytest.raises(MediaItem.NotFound):
            await media_item_repo.list_categories(media_item_id)


class TestListDeleted:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        items = [
            await media_item_factory(user.id, deleted_at=timezone.now()),
            await media_item_factory(user.id, deleted_at=timezone.now()),
            await media_item_factory(user.id, deleted_at=None),
        ]
        # WHEN
        result = await media_item_repo.list_deleted(user.id, offset=0)
        # THEN
        assert result == [items[1], items[0]]


class TestSetCategories:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        item = await media_item_factory(user.id)
        categories_1 = [
            MediaItem.Category(
                name=MediaItem.Category.Name.ANIMALS,
                origin=MediaItem.Category.Origin.USER,
                probability=90,
            ),
            MediaItem.Category(
                name=MediaItem.Category.Name.PETS,
                origin=MediaItem.Category.Origin.USER,
                probability=100,
            ),
        ]
        categories_2 = [
            MediaItem.Category(
                name=MediaItem.Category.Name.PETS,
                origin=MediaItem.Category.Origin.USER,
                probability=80,
            ),
            MediaItem.Category(
                name=MediaItem.Category.Name.TRAVEL,
                origin=MediaItem.Category.Origin.USER,
                probability=90,
            ),
        ]
        categories_3: list[MediaItemCategory] = []
        # WHEN: setting categories for the first time
        await media_item_repo.set_categories(item.id, categories=categories_1)
        # THEN
        result = await _list_categories_by_id(item.id)
        assert result == categories_1

        # WHEN: changing categories to existing and newly one
        await media_item_repo.set_categories(item.id, categories=categories_2)
        # THEN
        result = await _list_categories_by_id(item.id)
        assert result == categories_2

        # WHEN: changing to empty list
        await media_item_repo.set_categories(item.id, categories=categories_3)
        # THEN
        result = await _list_categories_by_id(item.id)
        assert result == categories_3

    async def test_when_media_item_does_not_exist(
        self, media_item_repo: MediaItemRepository,
    ):
        media_item_id = uuid.uuid7()
        with pytest.raises(MediaItem.NotFound):
            await media_item_repo.set_categories(media_item_id, categories=[])

    async def test_with_empty_categories(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        item = await media_item_factory(user.id)
        categories = [
            MediaItem.Category(
                name=MediaItem.Category.Name.ANIMALS,
                origin=MediaItem.Category.Origin.USER,
                probability=90,
            ),
        ]
        await _add_category(item.id, categories[0])
        # WHEN
        await media_item_repo.set_categories(item.id, categories=[])
        # THEN
        result = await _list_categories_by_id(item.id)
        assert result == []


class TestSetDeletedAtBatch:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        deleted_at = timezone.now()
        items = [
            await media_item_factory(user.id, deleted_at=None),
            await media_item_factory(user.id, deleted_at=None),
        ]
        ids = [item.id for item in items]
        # WHEN
        result = await media_item_repo.set_deleted_at_batch(
            user.id, ids, deleted_at
        )
        # THEN
        assert result[0].deleted_at == deleted_at
        assert result[1].deleted_at == deleted_at
