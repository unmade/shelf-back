from __future__ import annotations

import operator
import os.path
import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.photos.domain import MediaItem
from app.config import config
from app.infrastructure.database.edgedb.db import db_context
from app.infrastructure.database.edgedb.repositories.media_item import (
    _dump_category,
    _load_category,
)
from app.toolkit import timezone
from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.domain import Namespace
    from app.app.photos.domain.media_item import MediaItemCategory
    from app.app.users.domain import User
    from app.infrastructure.database.edgedb.repositories import MediaItemRepository
    from tests.infrastructure.database.edgedb.conftest import (
        BookmarkFactory,
        FileFactory,
        MediaItemFactory,
    )

pytestmark = [pytest.mark.anyio, pytest.mark.database]


async def _add_category(file_id: UUID, category: MediaItemCategory) -> None:
    query = """
        WITH
            category := <json>$category
        UPDATE
            File
        FILTER
            .id = <uuid>$file_id
        SET {
            categories += (
                INSERT FileCategory {
                    name := <str>category['name'],
                    @origin := <int16>category['origin'],
                    @probability := <int16>category['probability'],
                }
            )
        }
    """

    await db_context.get().query_required_single(
        query,
        file_id=file_id,
        category=_dump_category(category),
    )


async def _list_categories_by_id(file_id: UUID) -> list[MediaItemCategory]:
    query = """
        SELECT
            File {
                categories: { name, @origin, @probability },
            }
        FILTER
            .id = <uuid>$file_id
    """

    obj = await db_context.get().query_required_single(query, file_id=file_id)
    return [
        _load_category(category)
        for category in obj.categories
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
        item_1 = await media_item_factory(user.id)
        categories_1 = [
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

        item_2 = await media_item_factory(user.id)
        categories_2 = [
            MediaItem.Category(
                name=MediaItem.Category.Name.ANIMALS,
                origin=MediaItem.Category.Origin.AUTO,
                probability=66,
            ),
            MediaItem.Category(
                name=MediaItem.Category.Name.LANDSCAPES,
                origin=MediaItem.Category.Origin.AUTO,
                probability=33,
            ),
        ]

        # WHEN: adding categories for the first time
        await media_item_repo.add_category_batch(item_1.file_id, categories_1)
        # THEN
        categories = await _list_categories_by_id(item_1.file_id)
        assert categories == categories_1

        # WHEN: adding existing categories
        await media_item_repo.add_category_batch(item_2.file_id, categories_2)
        # THEN
        categories = await _list_categories_by_id(item_2.file_id)
        assert categories == categories_2

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
        result = await media_item_repo.list_by_user_id(user.id, offset=0)
        # THEN
        assert result == sorted(
            items[::1],
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
                probability=100,
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
                probability=100,
            ),
            MediaItem.Category(
                name=MediaItem.Category.Name.TRAVEL,
                origin=MediaItem.Category.Origin.USER,
                probability=100,
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
