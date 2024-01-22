from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.photos.domain import MediaItem

if TYPE_CHECKING:
    from app.app.photos.services import MediaItemService

pytestmark = [pytest.mark.anyio]


class TestAutoAddCategoryBatch:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        file_id = uuid.uuid4()
        categories = [
            (MediaItem.Category.Name.ANIMALS, 92),
            (MediaItem.Category.Name.PETS, 94),
        ]
        db = cast(mock.MagicMock, media_item_service.db)
        # WHEN
        await media_item_service.auto_add_category_batch(file_id, categories)
        # THEN
        db.media_item.add_category_batch.assert_awaited_once_with(
            file_id,
            categories=[
                MediaItem.Category(
                    name=MediaItem.Category.Name.ANIMALS,
                    origin=MediaItem.Category.Origin.AUTO,
                    probability=92,
                ),
                MediaItem.Category(
                    name=MediaItem.Category.Name.PETS,
                    origin=MediaItem.Category.Origin.AUTO,
                    probability=94,
                ),
            ]
        )


class TestListForUser:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        user_id = uuid.uuid4()
        db = cast(mock.AsyncMock, media_item_service.db)
        # WHEN
        result = await media_item_service.list_for_user(user_id, offset=100, limit=50)
        # THEN
        assert result == db.media_item.list_by_user_id.return_value
        db.media_item.list_by_user_id.assert_awaited_once_with(
            user_id, offset=100, limit=50
        )
