from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.photos.domain import MediaItem

if TYPE_CHECKING:
    from app.app.photos.usecases import PhotosUseCase

pytestmark = [pytest.mark.anyio]


class TestAutoAddCategoryBatch:
    async def test(self, photos_use_case: PhotosUseCase):
        # GIVEN
        file_id = uuid.uuid4()
        categories = [
            (MediaItem.Category.Name.ANIMALS, 92),
            (MediaItem.Category.Name.PETS, 94),
        ]
        media_item_service = cast(mock.MagicMock, photos_use_case.media_item)
        # WHEN
        await photos_use_case.auto_add_category_batch(file_id, categories)
        # THEN
        media_item_service.auto_add_category_batch.assert_awaited_once_with(
            file_id, categories=categories
        )


class TestListMediaItems:
    async def test(self, photos_use_case: PhotosUseCase):
        # GIVEN
        user_id = uuid.uuid4()
        media_item_service = cast(mock.MagicMock, photos_use_case.media_item)
        # WHEN
        result = await photos_use_case.list_media_items(user_id, offset=0, limit=25)
        # THEN
        assert result == media_item_service.list_for_user.return_value
        media_item_service.list_for_user.assert_awaited_once_with(
            user_id, only_favourites=False, offset=0, limit=25
        )


class TestListMediaItemCategories:
    async def test(self, photos_use_case: PhotosUseCase):
        # GIVEN
        user_id, file_id = uuid.uuid4(), uuid.uuid4()
        media_item_service = cast(mock.MagicMock, photos_use_case.media_item)
        # WHEN
        result = await photos_use_case.list_media_item_categories(user_id, file_id)
        # THEN
        assert result == media_item_service.list_categories.return_value
        media_item_service.get_for_user.assert_awaited_once_with(user_id, file_id)
        item = media_item_service.get_for_user.return_value
        media_item_service.list_categories.assert_awaited_once_with(item.file_id)


class TestSetCategories:
    async def test(self, photos_use_case: PhotosUseCase):
        # GIVEN
        user_id, file_id = uuid.uuid4(), uuid.uuid4()
        media_item_service = cast(mock.MagicMock, photos_use_case.media_item)
        categories = [MediaItem.Category.Name.ANIMALS, MediaItem.Category.Name.PETS]
        # WHEN
        await photos_use_case.set_media_item_categories(
            user_id, file_id, categories=categories
        )
        # THEN
        media_item_service.get_for_user.assert_awaited_once_with(user_id, file_id)
        item = media_item_service.get_for_user.return_value
        media_item_service.set_categories.assert_awaited_once_with(
            item.file_id, categories
        )
