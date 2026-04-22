from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast
from unittest import mock

import freezegun
import pytest

from app.app.blobs.domain import Blob
from app.app.blobs.domain.content import IBlobContent
from app.app.infrastructure.database import SENTINEL_ID
from app.app.infrastructure.storage import DownloadBatchItem
from app.app.photos.domain import MediaItem
from app.app.photos.services.media_item import (
    DownloadMediaItem,
    DownloadSessionInfo,
    _make_storage_key,
)
from app.toolkit import timezone
from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from datetime import datetime
    from unittest.mock import MagicMock

    from app.app.photos.services import MediaItemService

pytestmark = [pytest.mark.anyio]


def _make_blob(storage_key: str, created_at: datetime | None = None) -> Blob:
    return Blob(
        id=uuid.uuid7(),
        storage_key=storage_key,
        size=123,
        chash=uuid.uuid7().hex,
        media_type=MediaType.IMAGE_JPEG,
        created_at=created_at or timezone.now(),
    )


def _make_media_item(
    name: str | None = None,
    media_type: str | None = None,
    owner_id: uuid.UUID | None = None,
) -> MediaItem:
    return MediaItem(
        id=uuid.uuid7(),
        owner_id=owner_id or uuid.uuid7(),
        blob_id=uuid.uuid7(),
        name=name or f"{uuid.uuid4().hex}.jpeg",
        size=123,
        media_type=media_type or MediaType.IMAGE_JPEG,
        chash=uuid.uuid4().hex,
        taken_at=None,
        created_at=timezone.now(),
        modified_at=timezone.now(),
        deleted_at=None,
    )


def _make_download_media_item(
    storage_key: str,
    name: str,
    media_type: str = MediaType.IMAGE_JPEG,
) -> DownloadMediaItem:
    return DownloadMediaItem(
        storage_key=storage_key,
        name=name,
        media_type=media_type,
        size=123,
        modified_at=timezone.now(),
    )


def _make_photo_storage_key(name: str) -> str:
    return f"owner_id/photos/2026/04/20/{name}"


class TestAutoAddCategoryBatch:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        media_item_id = uuid.uuid7()
        categories = [
            (MediaItem.Category.Name.ANIMALS, 92),
            (MediaItem.Category.Name.PETS, 94),
        ]
        db = cast(mock.MagicMock, media_item_service.db)
        # WHEN
        await media_item_service.auto_add_category_batch(media_item_id, categories)
        # THEN
        db.media_item.add_category_batch.assert_awaited_once_with(
            media_item_id,
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
        user_id = uuid.uuid7()
        db = cast(mock.AsyncMock, media_item_service.db)
        # WHEN
        result = await media_item_service.count(user_id)
        # THEN
        assert result == db.media_item.count.return_value
        db.media_item.count.assert_awaited_once_with(user_id)


class TestCreate:
    @mock.patch("app.app.photos.services.media_item._make_storage_key")
    async def test(
        self,
        make_storage_key_mock: MagicMock,
        media_item_service: MediaItemService,
        content: IBlobContent,
    ):
        # GIVEN
        owner_id = uuid.uuid7()
        name = "photo.jpg"
        media_type = MediaType.IMAGE_JPEG
        storage_key = f"{owner_id}/photos/2026/04/19/prefix_{name}"
        created_at = datetime(2026, 4, 19, 10, 11, 12, tzinfo=UTC)
        blob = _make_blob(storage_key, created_at=created_at)
        db = cast(mock.AsyncMock, media_item_service.db)
        blob_service = cast(mock.MagicMock, media_item_service.blob_service)
        make_storage_key_mock.return_value = storage_key
        blob_service.create.return_value = blob
        # WHEN
        with freezegun.freeze_time(created_at, real_asyncio=True):
            result = await media_item_service.create(
                owner_id, name, content, media_type
            )
        # THEN
        assert result == db.media_item.save.return_value
        make_storage_key_mock.assert_called_once_with(owner_id, name)
        blob_service.create.assert_awaited_once_with(storage_key, content, media_type)
        db.media_item.save.assert_awaited_once_with(
            MediaItem(
                id=SENTINEL_ID,
                owner_id=owner_id,
                blob_id=blob.id,
                name=name,
                media_type=blob.media_type,
                size=blob.size,
                chash=blob.chash,
                created_at=created_at,
                modified_at=created_at,
            )
        )


class TestCreateDownloadSession:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        owner_id = uuid.uuid7()
        ids = [uuid.uuid7(), uuid.uuid7()]
        items = (
            _make_download_media_item(
                storage_key=_make_photo_storage_key("photo.jpg"),
                name="photo.jpg",
            ),
            _make_download_media_item(
                storage_key=_make_photo_storage_key("scan.png"),
                name="scan.png",
            ),
        )
        get_download_items = mock.AsyncMock(return_value=items)
        # WHEN
        with mock.patch.object(
            type(media_item_service),
            "_get_download_items",
            get_download_items,
        ):
            result = await media_item_service.create_download_session(owner_id, ids)
            cached = await media_item_service.get_download_session(result.key)
        # THEN
        assert result == DownloadSessionInfo(key=result.key, items_count=2)
        get_download_items.assert_awaited_once_with(owner_id, ids)
        assert cached == items
        assert await media_item_service.get_download_session(result.key) is None

    async def test_when_no_items_are_downloadable(
        self, media_item_service: MediaItemService
    ):
        # GIVEN
        get_download_items = mock.AsyncMock(return_value=())
        # WHEN / THEN
        with mock.patch.object(
            type(media_item_service),
            "_get_download_items",
            get_download_items,
        ), pytest.raises(MediaItem.NotFound):
            await media_item_service.create_download_session(
                uuid.uuid7(), [uuid.uuid7()]
            )


class TestDeleteBatch:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        user_id, media_item_ids = uuid.uuid7(), [uuid.uuid7(), uuid.uuid7()]
        deleted_at = datetime(2026, 4, 19, 10, 11, 12, tzinfo=UTC)
        db = cast(mock.AsyncMock, media_item_service.db)
        # WHEN
        with freezegun.freeze_time(deleted_at, real_asyncio=True):
            result = await media_item_service.delete_batch(user_id, media_item_ids)
        # THEN
        assert result == db.media_item.set_deleted_at_batch.return_value
        db.media_item.set_deleted_at_batch.assert_awaited_once_with(
            user_id, media_item_ids, deleted_at=deleted_at
        )


class TestDeletePermanently:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        ids = [uuid.uuid7(), uuid.uuid7()]
        blob_ids = [uuid.uuid7(), uuid.uuid7()]
        db = cast(mock.AsyncMock, media_item_service.db)
        blob_service = cast(mock.MagicMock, media_item_service.blob_service)
        db.media_item.get_by_id_batch.return_value = [
            mock.Mock(blob_id=blob_id)
            for blob_id in blob_ids
        ]
        # WHEN
        await media_item_service.delete_permanently(ids)
        # THEN
        db.media_item.get_by_id_batch.assert_awaited_once_with(ids)
        db.media_item.delete_batch.assert_awaited_once_with(ids)
        blob_service.delete_batch.assert_awaited_once_with(blob_ids)


class TestDownload:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        item = _make_download_media_item(
            storage_key=_make_photo_storage_key("photo.jpg"),
            name="photo.jpg",
        )
        blob_service = cast(mock.MagicMock, media_item_service.blob_service)
        # WHEN
        result = media_item_service.download(item)
        # THEN
        assert result == blob_service.download.return_value
        blob_service.download.assert_called_once_with(item.storage_key)


class TestDownloadBatch:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        item_a = _make_download_media_item(
            storage_key=_make_photo_storage_key("photo.jpg"),
            name="photo.jpg",
        )
        item_b = _make_download_media_item(
            storage_key=_make_photo_storage_key("scan.png"),
            name="scan.png",
            media_type=MediaType.IMAGE_PNG,
        )
        blob_service = cast(mock.MagicMock, media_item_service.blob_service)
        expected_items = [
            DownloadBatchItem(
                key=item_a.storage_key,
                is_dir=False,
                archive_path=item_a.name,
            ),
            DownloadBatchItem(
                key=item_b.storage_key,
                is_dir=False,
                archive_path=item_b.name,
            ),
        ]
        # WHEN
        result = media_item_service.download_batch((item_a, item_b))
        # THEN
        assert result == blob_service.download_batch.return_value
        blob_service.download_batch.assert_called_once_with(expected_items)


class TestGetByIDBatch:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        media_item_ids = [uuid.uuid7(), uuid.uuid7()]
        db = cast(mock.AsyncMock, media_item_service.db)
        # WHEN
        result = await media_item_service.get_by_id_batch(media_item_ids)
        # THEN
        assert result == db.media_item.get_by_id_batch.return_value
        db.media_item.get_by_id_batch.assert_awaited_once_with(media_item_ids)


class TestGetDownloadItems:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        owner_id = uuid.uuid7()
        item_a = _make_media_item(name="photo.jpg", owner_id=owner_id)
        item_b = _make_media_item(
            name="scan.png",
            media_type=MediaType.IMAGE_PNG,
            owner_id=owner_id,
        )
        blob_a = _make_blob("owner_id/photos/2026/04/20/photo.jpg")
        blob_b = _make_blob("owner_id/photos/2026/04/20/scan.png")
        item_a.blob_id = blob_a.id
        item_b.blob_id = blob_b.id

        db = cast(mock.AsyncMock, media_item_service.db)
        blob_service = cast(mock.MagicMock, media_item_service.blob_service)
        foreign_item = _make_media_item(name="ignore.jpg")
        db.media_item.get_by_id_batch.return_value = [item_b, foreign_item, item_a]
        blob_service.get_by_id_batch.return_value = [blob_b, blob_a]

        # WHEN
        result = await media_item_service._get_download_items(
            owner_id, [item_a.id, item_b.id, item_a.id]
        )

        # THEN
        assert result == (
            DownloadMediaItem(
                storage_key=blob_b.storage_key,
                name=item_b.name,
                media_type=item_b.media_type,
                size=item_b.size,
                modified_at=item_b.modified_at,
            ),
            DownloadMediaItem(
                storage_key=blob_a.storage_key,
                name=item_a.name,
                media_type=item_a.media_type,
                size=item_a.size,
                modified_at=item_a.modified_at,
            ),
        )
        db.media_item.get_by_id_batch.assert_awaited_once_with([item_a.id, item_b.id])
        blob_service.get_by_id_batch.assert_awaited_once_with([blob_b.id, blob_a.id])

    async def test_when_no_blob_matches_accessible_items(
        self, media_item_service: MediaItemService
    ):
        # GIVEN
        owner_id = uuid.uuid7()
        item = _make_media_item(owner_id=owner_id)
        db = cast(mock.AsyncMock, media_item_service.db)
        blob_service = cast(mock.MagicMock, media_item_service.blob_service)
        db.media_item.get_by_id_batch.return_value = [item]
        blob_service.get_by_id_batch.return_value = []

        # WHEN / THEN
        with pytest.raises(MediaItem.NotFound):
            await media_item_service._get_download_items(owner_id, [item.id])

        blob_service.get_by_id_batch.assert_awaited_once_with([item.blob_id])

    async def test_when_no_items_belong_to_owner(
        self, media_item_service: MediaItemService
    ):
        # GIVEN
        owner_id = uuid.uuid7()
        db = cast(mock.AsyncMock, media_item_service.db)
        blob_service = cast(mock.MagicMock, media_item_service.blob_service)
        db.media_item.get_by_id_batch.return_value = [_make_media_item()]

        # WHEN / THEN
        with pytest.raises(MediaItem.NotFound):
            await media_item_service._get_download_items(owner_id, [uuid.uuid7()])

        blob_service.get_by_id_batch.assert_not_awaited()


class TestGetDownloadSession:
    async def test_when_session_does_not_exist(
        self, media_item_service: MediaItemService
    ):
        assert await media_item_service.get_download_session(uuid.uuid7().hex) is None


class TestGetForUser:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        user_id, media_item_id = uuid.uuid7(), uuid.uuid7()
        db = cast(mock.AsyncMock, media_item_service.db)
        # WHEN
        result = await media_item_service.get_for_owner(user_id, media_item_id)
        # THEN
        assert result == db.media_item.get_for_owner.return_value
        db.media_item.get_for_owner.assert_awaited_once_with(user_id, media_item_id)


class TestIterDeleted:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        user_id = uuid.uuid7()
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


class TestListCategories:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        media_item_id = uuid.uuid7()
        db = cast(mock.AsyncMock, media_item_service.db)
        # WHEN
        result = await media_item_service.list_categories(media_item_id)
        # THEN
        assert result == db.media_item.list_categories.return_value
        db.media_item.list_categories.assert_awaited_once_with(media_item_id)


class TestListDeleted:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        user_id = uuid.uuid7()
        db = cast(mock.AsyncMock, media_item_service.db)
        # WHEN
        result = await media_item_service.list_deleted(user_id, offset=0, limit=50)
        # THEN
        assert result == db.media_item.list_deleted.return_value
        db.media_item.list_deleted.assert_awaited_once_with(user_id, offset=0, limit=50)


class TestListFavouriteIDs:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        user_id = uuid.uuid7()
        db = cast(mock.AsyncMock, media_item_service.db)
        # WHEN
        result = await media_item_service.list_favourite_ids(user_id)
        # THEN
        assert result == db.media_item_favourite.list_ids.return_value
        db.media_item_favourite.list_ids.assert_awaited_once_with(user_id)


class TestListForUser:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        user_id = uuid.uuid7()
        db = cast(mock.AsyncMock, media_item_service.db)
        # WHEN
        result = await media_item_service.list_(user_id, offset=100, limit=50)
        # THEN
        assert result == db.media_item.list_by_owner.return_value
        db.media_item.list_by_owner.assert_awaited_once_with(
            user_id, only_favourites=False, offset=100, limit=50
        )


class TestMakeStorageKey:
    @mock.patch("app.app.photos.services.media_item.uuid.uuid7")
    def test(self, uuid7_mock: MagicMock):
        # GIVEN
        owner_id = uuid.UUID("01234567-89ab-cdef-0123-456789abcdef")
        now = datetime(2026, 4, 19, 10, 11, 12, tzinfo=UTC)
        uuid7_mock.return_value.hex = "0123456789abcdef0123456789abcdef"
        # WHEN
        with freezegun.freeze_time(now):
            result = _make_storage_key(owner_id, "photo.jpg")
        # THEN
        assert result == (
            f"{owner_id}/photos/2026/04/19/89abcdef_photo.jpg"
        )


class TestMarkFavouriteBatch:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        user_id = uuid.uuid7()
        ids = [uuid.uuid7(), uuid.uuid7()]
        db = cast(mock.AsyncMock, media_item_service.db)
        db.media_item.get_by_id_batch.return_value = [
            mock.Mock(id=ids[0], owner_id=user_id),
            mock.Mock(id=uuid.uuid7(), owner_id=uuid.uuid7()),
            mock.Mock(id=ids[1], owner_id=user_id),
        ]
        # WHEN
        await media_item_service.mark_favourite_batch(user_id, ids)
        # THEN
        db.media_item.get_by_id_batch.assert_awaited_once_with(ids)
        db.media_item_favourite.add_batch.assert_awaited_once_with(user_id, ids)

    async def test_when_no_accessible_items(self, media_item_service: MediaItemService):
        # GIVEN
        user_id = uuid.uuid7()
        ids = [uuid.uuid7(), uuid.uuid7()]
        db = cast(mock.AsyncMock, media_item_service.db)
        db.media_item.get_by_id_batch.return_value = [
            mock.Mock(id=uuid.uuid7(), owner_id=uuid.uuid7()),
        ]
        # WHEN
        await media_item_service.mark_favourite_batch(user_id, ids)
        # THEN
        db.media_item.get_by_id_batch.assert_awaited_once_with(ids)
        db.media_item_favourite.add_batch.assert_not_awaited()


class TestRestoreBatch:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        user_id, media_item_ids = uuid.uuid7(), [uuid.uuid7(), uuid.uuid7()]
        db = cast(mock.AsyncMock, media_item_service.db)
        deleted_at = None
        # WHEN
        result = await media_item_service.restore_batch(user_id, media_item_ids)
        # THEN
        assert result == db.media_item.set_deleted_at_batch.return_value
        db.media_item.set_deleted_at_batch.assert_awaited_once_with(
            user_id, media_item_ids, deleted_at=deleted_at
        )


class TestSetCategories:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        media_item_id = uuid.uuid7()
        categories = [
            MediaItem.Category.Name.ANIMALS,
            MediaItem.Category.Name.PETS,
        ]
        db = cast(mock.MagicMock, media_item_service.db)
        # WHEN
        await media_item_service.set_categories(media_item_id, categories)
        # THEN
        db.media_item.set_categories.assert_awaited_once_with(
            media_item_id,
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


class TestUnmarkFavouriteBatch:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        user_id = uuid.uuid7()
        ids = [uuid.uuid7(), uuid.uuid7()]
        db = cast(mock.AsyncMock, media_item_service.db)
        # WHEN
        await media_item_service.unmark_favourite_batch(user_id, ids)
        # THEN
        db.media_item_favourite.remove_batch.assert_awaited_once_with(user_id, ids)
