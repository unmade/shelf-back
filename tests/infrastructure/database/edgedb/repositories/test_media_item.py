from __future__ import annotations

import operator
import os.path
import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.photos.domain import MediaItem
from app.config import config
from app.infrastructure.database.edgedb.db import db_context
from app.infrastructure.database.edgedb.repositories.media_item import _load_category
from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.domain import Namespace
    from app.app.photos.domain.media_item import MediaItemCategory
    from app.app.users.domain import User
    from app.infrastructure.database.edgedb.repositories import MediaItemRepository
    from tests.infrastructure.database.edgedb.conftest import (
        FileFactory,
        MediaItemFactory,
    )

pytestmark = [pytest.mark.anyio, pytest.mark.database]


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
        items = [
            await media_item_factory(user.id, "im.jpg", mediatype=MediaType.IMAGE_JPEG),
            await media_item_factory(user.id, "im.png", mediatype=MediaType.IMAGE_PNG),
        ]
        # WHEN
        result = await media_item_repo.list_by_user_id(user.id, offset=0)
        # THEN
        assert result == sorted(items, key=operator.attrgetter("mtime"), reverse=True)
