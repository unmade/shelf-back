from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, TypeVar, cast
from unittest import mock

import pytest

from app.app.photos.domain import MediaItem

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.photos.services import MediaItemService

pytestmark = [pytest.mark.anyio]

T = TypeVar("T")


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


class TestCount:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        user_id = uuid.uuid4()
        db = cast(mock.AsyncMock, media_item_service.db)
        # WHEN
        result = await media_item_service.count(user_id)
        # THEN
        assert result == db.media_item.count.return_value
        db.media_item.count.assert_awaited_once_with(user_id)



class TestDeleteBatch:
    @mock.patch("app.app.photos.services.media_item.timezone")
    async def test(
        self, timezone_mock: MagicMock, media_item_service: MediaItemService
    ):
        # GIVEN
        user_id, file_ids = uuid.uuid4(), [uuid.uuid4(), uuid.uuid4()]
        db = cast(mock.AsyncMock, media_item_service.db)
        deleted_at = timezone_mock.now.return_value
        # WHEN
        result = await media_item_service.delete_batch(user_id, file_ids)
        # THEN
        assert result == db.media_item.set_deleted_at_batch.return_value
        db.media_item.set_deleted_at_batch.assert_awaited_once_with(
            user_id, file_ids, deleted_at=deleted_at
        )


class TestGetForUser:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        user_id, file_id = uuid.uuid4(), uuid.uuid4()
        db = cast(mock.AsyncMock, media_item_service.db)
        # WHEN
        result = await media_item_service.get_for_user(user_id, file_id)
        # THEN
        assert result == db.media_item.get_by_user_id.return_value
        db.media_item.get_by_user_id.assert_awaited_once_with(user_id, file_id)


class TestGetByIDBatch:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        file_ids = [uuid.uuid4(), uuid.uuid4()]
        db = cast(mock.AsyncMock, media_item_service.db)
        # WHEN
        result = await media_item_service.get_by_id_batch(file_ids)
        # THEN
        assert result == db.media_item.get_by_id_batch.return_value
        db.media_item.get_by_id_batch.assert_awaited_once_with(file_ids)


class TestIterDeleted:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        user_id = uuid.uuid4()
        batches = [[mock.MagicMock(), mock.MagicMock()], [mock.MagicMock()], []]
        db = cast(mock.AsyncMock, media_item_service.db)
        db.media_item.list_deleted.side_effect = batches
        # WHEN
        result = []
        async for batch in media_item_service.iter_deleted(user_id, batch_size=2):
            result.append(batch)
        # THEN
        assert result == batches[:2]
        db.media_item.list_deleted.assert_has_awaits([
            mock.call(user_id, offset=0, limit=2),
            mock.call(user_id, offset=2, limit=2),
        ])


class TestListDeleted:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        user_id = uuid.uuid4()
        db = cast(mock.AsyncMock, media_item_service.db)
        # WHEN
        result = await media_item_service.list_deleted(user_id, offset=0, limit=50)
        # THEN
        assert result == db.media_item.list_deleted.return_value
        db.media_item.list_deleted.assert_awaited_once_with(user_id, offset=0, limit=50)


class TestListForUser:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        user_id = uuid.uuid4()
        db = cast(mock.AsyncMock, media_item_service.db)
        # WHEN
        result = await media_item_service.list_(user_id, offset=100, limit=50)
        # THEN
        assert result == db.media_item.list_by_user_id.return_value
        db.media_item.list_by_user_id.assert_awaited_once_with(
            user_id, only_favourites=False, offset=100, limit=50
        )


class TestListCategories:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        file_id = uuid.uuid4()
        db = cast(mock.AsyncMock, media_item_service.db)
        # WHEN
        result = await media_item_service.list_categories(file_id)
        # THEN
        assert result == db.media_item.list_categories.return_value
        db.media_item.list_categories.assert_awaited_once_with(file_id)


class TestRestoreBatch:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        user_id, file_ids = uuid.uuid4(), [uuid.uuid4(), uuid.uuid4()]
        db = cast(mock.AsyncMock, media_item_service.db)
        deleted_at = None
        # WHEN
        result = await media_item_service.restore_batch(user_id, file_ids)
        # THEN
        assert result == db.media_item.set_deleted_at_batch.return_value
        db.media_item.set_deleted_at_batch.assert_awaited_once_with(
            user_id, file_ids, deleted_at=deleted_at
        )


class TestSetCategories:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        file_id = uuid.uuid4()
        categories = [
            MediaItem.Category.Name.ANIMALS,
            MediaItem.Category.Name.PETS,
        ]
        db = cast(mock.MagicMock, media_item_service.db)
        # WHEN
        await media_item_service.set_categories(file_id, categories)
        # THEN
        db.media_item.set_categories.assert_awaited_once_with(
            file_id,
            categories=[
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
        )
