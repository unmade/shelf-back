from __future__ import annotations

import operator
import os.path
import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.photos.domain import MediaItem
from app.app.photos.domain.media_item import MediaItemCategoryName
from app.config import config
from app.infrastructure.database.tortoise import models
from app.toolkit import timezone
from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.domain import Namespace
    from app.app.photos.domain.media_item import MediaItemCategory
    from app.app.users.domain import User
    from app.infrastructure.database.tortoise.repositories import MediaItemRepository
    from tests.infrastructure.database.tortoise.conftest import (
        BookmarkFactory,
        FileFactory,
        MediaItemFactory,
    )

pytestmark = [pytest.mark.anyio, pytest.mark.database]


_ORIGIN_TO_INT = {
    MediaItem.Category.Origin.AUTO: 0,
    MediaItem.Category.Origin.USER: 1,
}

_INT_TO_ORIGIN = dict(zip(_ORIGIN_TO_INT.values(), _ORIGIN_TO_INT.keys(), strict=False))


async def _add_category(file_id: UUID, category: MediaItemCategory) -> None:
    cat_obj, _ = await models.FileCategory.get_or_create(name=category.name)
    await models.FileFileCategoryThrough.create(
        file_id=file_id,
        file_category=cat_obj,
        origin=_ORIGIN_TO_INT[category.origin],
        probability=category.probability,
    )


async def _list_categories_by_id(file_id: UUID) -> list[MediaItemCategory]:
    through_objs = await (
        models.FileFileCategoryThrough
        .filter(file_id=file_id)
        .select_related("file_category")
        .order_by("probability")
    )
    return [
        MediaItem.Category(
            name=MediaItemCategoryName(obj.file_category.name),
            origin=_INT_TO_ORIGIN[obj.origin],
            probability=obj.probability,
        )
        for obj in through_objs
    ]


class TestAddCategoryBatch:
    @pytest.mark.usefixtures("namespace")
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
        await media_item_repo.add_category_batch(item.file_id, categories)
        # THEN
        result = await _list_categories_by_id(item.file_id)
        assert result == categories

    @pytest.mark.usefixtures("namespace")
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
        await media_item_repo.add_category_batch(item.file_id, existing_categories)

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
        await media_item_repo.add_category_batch(item.file_id, new_categories)
        # THEN: LANDSCAPES unchanged, ANIMALS updated, PETS added
        result = await _list_categories_by_id(item.file_id)
        assert len(result) == 3
        assert result == [
            existing_categories[0],
            new_categories[0],
            new_categories[1],
        ]

    @pytest.mark.usefixtures("namespace")
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
        await media_item_repo.add_category_batch(item.file_id, categories)

        updated_categories = [
            MediaItem.Category(
                name=MediaItem.Category.Name.ANIMALS,
                origin=MediaItem.Category.Origin.AUTO,
                probability=90,
            ),
        ]
        # WHEN
        await media_item_repo.add_category_batch(item.file_id, updated_categories)
        # THEN
        result = await _list_categories_by_id(item.file_id)
        assert result == updated_categories

    @pytest.mark.usefixtures("namespace")
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
        await _add_category(item.file_id, categories[0])
        # WHEN
        await media_item_repo.add_category_batch(item.file_id, categories=[])
        # THEN
        assert await _list_categories_by_id(item.file_id) == categories

    async def test_when_media_item_does_not_exist(
        self,
        media_item_repo: MediaItemRepository,
    ):
        # GIVEN
        file_id = uuid.uuid4()
        # WHEN / THEN
        with pytest.raises(MediaItem.NotFound):
            await media_item_repo.add_category_batch(file_id, categories=[])


class TestCount:
    @pytest.mark.usefixtures("namespace")
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


class TestGetByIDBatch:
    @pytest.mark.usefixtures("namespace")
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
        file_ids = [item.file_id for item in items[:2]]
        # WHEN
        result = await media_item_repo.get_by_id_batch(file_ids)
        # THEN
        assert result == list(reversed(items[:2]))


class TestGetByUserID:
    @pytest.mark.usefixtures("namespace")
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        media_item = await media_item_factory(user.id)
        # WHEN
        result = await media_item_repo.get_by_user_id(user.id, media_item.file_id)
        # THEN
        assert result == media_item

    async def test_when_media_item_does_not_exist(
        self, media_item_repo: MediaItemRepository, user: User,
    ):
        file_id = uuid.uuid4()
        with pytest.raises(MediaItem.NotFound):
            await media_item_repo.get_by_user_id(user.id, file_id)


class TestListByUserID:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        file_factory: FileFactory,
        namespace: Namespace,
        user: User,
    ):
        # GIVEN
        await file_factory(
            namespace.path,
            os.path.join(config.features.photos_library_path, "f.txt"),
        )
        await media_item_factory(user.id, deleted_at=timezone.now()),
        items = [
            await media_item_factory(user.id, "im.jpg", mediatype=MediaType.IMAGE_JPEG),
            await media_item_factory(user.id, "im.png", mediatype=MediaType.IMAGE_PNG),
        ]
        # WHEN
        result = await media_item_repo.list_by_user_id(user.id, offset=0)
        # THEN
        assert result == list(reversed(items))

    async def test_only_favourites(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        bookmark_factory: BookmarkFactory,
        file_factory: FileFactory,
        namespace: Namespace,
        user: User,
    ):
        # GIVEN
        file = await file_factory(
            namespace.path,
            os.path.join(config.features.photos_library_path, "f.txt"),
        )
        items = [
            await media_item_factory(user.id, "im.jpg", mediatype=MediaType.IMAGE_JPEG),
            await media_item_factory(user.id, "im.png", mediatype=MediaType.IMAGE_PNG),
            await media_item_factory(user.id, "i.heic", mediatype=MediaType.IMAGE_HEIC),
        ]
        await bookmark_factory(user.id, file.id)
        await bookmark_factory(user.id, items[0].file_id)
        await bookmark_factory(user.id, items[-1].file_id)
        # WHEN
        result = await media_item_repo.list_by_user_id(
            user.id, only_favourites=True, offset=0
        )
        # THEN
        assert result == sorted(
            [items[0], items[-1]],
            key=operator.attrgetter("modified_at"),
            reverse=True,
        )

    @pytest.mark.usefixtures("namespace")
    async def test_only_favourites_when_its_empty(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        await media_item_factory(user.id, "im.jpg", mediatype=MediaType.IMAGE_JPEG),
        await media_item_factory(user.id, "im.png", mediatype=MediaType.IMAGE_PNG),
        # WHEN
        result = await media_item_repo.list_by_user_id(
            user.id, only_favourites=True, offset=0
        )
        # THEN
        assert result == []


class TestListCategories:
    @pytest.mark.usefixtures("namespace")
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
        await _add_category(item.file_id, categories[0])
        await _add_category(item.file_id, categories[1])
        # WHEN
        result = await media_item_repo.list_categories(item.file_id)
        # THEN
        assert result == categories

    async def test_when_media_item_does_not_exist(
        self, media_item_repo: MediaItemRepository,
    ):
        file_id = uuid.uuid4()
        with pytest.raises(MediaItem.NotFound):
            await media_item_repo.list_categories(file_id)


class TestListDeleted:
    @pytest.mark.usefixtures("namespace")
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
    @pytest.mark.usefixtures("namespace")
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
        await media_item_repo.set_categories(item.file_id, categories=categories_1)
        # THEN
        result = await _list_categories_by_id(item.file_id)
        assert result == categories_1

        # WHEN: changing categories to existing and newly one
        await media_item_repo.set_categories(item.file_id, categories=categories_2)
        # THEN
        result = await _list_categories_by_id(item.file_id)
        assert result == categories_2

        # WHEN: changing to empty list
        await media_item_repo.set_categories(item.file_id, categories=categories_3)
        # THEN
        result = await _list_categories_by_id(item.file_id)
        assert result == categories_3

    @pytest.mark.usefixtures("namespace")
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
        await _add_category(item.file_id, categories[0])
        # WHEN
        await media_item_repo.set_categories(item.file_id, categories=[])
        # THEN
        result = await _list_categories_by_id(item.file_id)
        assert result == []

    async def test_when_media_item_does_not_exist(
        self, media_item_repo: MediaItemRepository,
    ):
        file_id = uuid.uuid4()
        with pytest.raises(MediaItem.NotFound):
            await media_item_repo.set_categories(file_id, categories=[])


class TestSetDeletedAtBatch:
    @pytest.mark.usefixtures("namespace")
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
        file_ids = [item.file_id for item in items]
        # WHEN
        result = await media_item_repo.set_deleted_at_batch(
            user.id, file_ids, deleted_at
        )
        # THEN
        assert result[0].deleted_at == deleted_at
        assert result[1].deleted_at == deleted_at
