from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.blobs.domain import BlobMetadata
from app.app.photos.domain import MediaItem
from app.app.photos.services.media_item import DownloadMediaItem, DownloadSessionInfo
from app.toolkit import timezone
from app.toolkit.mediatypes import MediaType
from app.toolkit.metadata import Exif

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from app.app.photos.usecases import MediaItemUseCase

pytestmark = [pytest.mark.anyio]


def _make_media_item(
    name: str | None = None,
    media_type: str | None = None,
    owner_id: UUID | None = None,
) -> MediaItem:
    return MediaItem(
        id=uuid.uuid7(),
        owner_id=owner_id or uuid.uuid7(),
        blob_id=uuid.uuid7(),
        name=name or f"{uuid.uuid4().hex}.jpeg",
        size=12,
        media_type=media_type or MediaType.IMAGE_JPEG,
        chash=uuid.uuid4().hex,
        taken_at=None,
        created_at=timezone.now(),
        modified_at=timezone.now(),
        deleted_at=None,
    )


def _make_download_media_item(name: str) -> DownloadMediaItem:
    return DownloadMediaItem(
        storage_key=f"owner_id/photos/2026/04/20/{name}",
        name=name,
        media_type=MediaType.IMAGE_JPEG,
        size=12,
        modified_at=timezone.now(),
    )


class TestAutoAddCategoryBatch:
    async def test(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        media_item_id = uuid.uuid7()
        categories = [
            (MediaItem.Category.Name.ANIMALS, 92),
            (MediaItem.Category.Name.PETS, 94),
        ]
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)
        # WHEN
        await media_item_use_case.auto_add_category_batch(media_item_id, categories)
        # THEN
        media_item_service.auto_add_category_batch.assert_awaited_once_with(
            media_item_id, categories=categories
        )


class TestCount:
    async def test(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        owner_id = uuid.uuid7()
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)
        # WHEN
        result = await media_item_use_case.count(owner_id)
        # THEN
        assert result == media_item_service.count.return_value
        media_item_service.count.assert_awaited_once_with(owner_id)


class TestCreateDownloadSession:
    async def test(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        owner_id = uuid.uuid7()
        ids = [uuid.uuid7(), uuid.uuid7()]
        result_value = DownloadSessionInfo(
            key=uuid.uuid4().hex,
            items_count=2,
        )
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)
        media_item_service.create_download_session.return_value = result_value

        # WHEN
        result = await media_item_use_case.create_download_session(owner_id, ids)

        # THEN
        assert result == result_value
        media_item_service.create_download_session.assert_awaited_once_with(
            owner_id, ids
        )


class TestDeleteBatch:
    async def test(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        owner_id = uuid.uuid7()
        ids = [uuid.uuid7(), uuid.uuid7()]
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)
        # WHEN
        result = await media_item_use_case.delete_batch(owner_id, ids)
        # THEN
        assert result == media_item_service.delete_batch.return_value
        media_item_service.delete_batch.assert_awaited_once_with(owner_id, ids)


class TestDeleteImmediatelyBatch:
    async def test(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        owner_id = uuid.uuid7()
        ids = [uuid.uuid7(), uuid.uuid7()]
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)
        media_item_service.get_by_id_batch.return_value = [
            MediaItem(
                id=item_id,
                owner_id=owner_id,
                blob_id=uuid.uuid7(),
                name=f"{uuid.uuid4().hex}.jpeg",
                size=12,
                media_type=MediaType.IMAGE_JPEG,
                chash=uuid.uuid4().hex,
                taken_at=None,
                created_at=_make_media_item().created_at,
                modified_at=_make_media_item().modified_at,
                deleted_at=None,
            )
            for item_id in ids
        ]

        # WHEN
        await media_item_use_case.delete_immediately_batch(owner_id, ids)

        # THEN
        media_item_service.get_by_id_batch.assert_awaited_once_with(ids)
        media_item_service.delete_permanently.assert_awaited_once_with(ids)

    async def test_when_owner_has_no_matching_media_items(
        self, media_item_use_case: MediaItemUseCase
    ):
        # GIVEN
        owner_id = uuid.uuid7()
        ids = [uuid.uuid7(), uuid.uuid7()]
        items = [_make_media_item() for _ in range(3)]
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)
        media_item_service.get_by_id_batch.return_value = items
        # WHEN
        await media_item_use_case.delete_immediately_batch(owner_id, ids)
        # THEN
        media_item_service.get_by_id_batch.assert_awaited_once_with(ids)
        media_item_service.delete_permanently.assert_not_awaited()


class TestDownload:
    async def test(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        item = _make_download_media_item("photo.jpg")
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)

        # WHEN
        result = media_item_use_case.download(item)

        # THEN
        assert result == media_item_service.download.return_value
        media_item_service.download.assert_called_once_with(item)


class TestDownloadBatch:
    async def test(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        session = (
            _make_download_media_item("photo.jpg"),
            _make_download_media_item("scan.png"),
        )
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)

        # WHEN
        result = media_item_use_case.download_batch(session)

        # THEN
        assert result == media_item_service.download_batch.return_value
        media_item_service.download_batch.assert_called_once_with(session)


class TestGetDownloadSession:
    async def test_when_there_is_no_session(
        self, media_item_use_case: MediaItemUseCase
    ):
        # GIVEN
        key = uuid.uuid4().hex
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)
        # WHEN
        result = await media_item_use_case.get_download_session(key)
        # THEN
        assert result == media_item_service.get_download_session.return_value
        media_item_service.get_download_session.assert_awaited_once_with(key)


class TestGetContentMetadata:
    async def test(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        owner_id = uuid.uuid7()
        item = _make_media_item(owner_id=owner_id)
        metadata = BlobMetadata(
            blob_id=item.blob_id,
            data=Exif(width=1280, height=800),
        )
        blob_metadata_service = cast(mock.MagicMock, media_item_use_case.blob_metadata)
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)
        media_item_service.get_for_owner.return_value = item
        blob_metadata_service.get_by_blob_id.return_value = metadata

        # WHEN
        result = await media_item_use_case.get_content_metadata(owner_id, item.id)

        # THEN
        assert result == metadata
        media_item_service.get_for_owner.assert_awaited_once_with(owner_id, item.id)
        blob_metadata_service.get_by_blob_id.assert_awaited_once_with(item.blob_id)


class TestList:
    async def test(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        owner_id = uuid.uuid7()
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)
        # WHEN
        result = await media_item_use_case.list_(owner_id, offset=0, limit=25)
        # THEN
        assert result == media_item_service.list_.return_value
        media_item_service.list_.assert_awaited_once_with(
            owner_id, only_favourites=False, offset=0, limit=25
        )

    async def test_only_favourites(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        owner_id = uuid.uuid7()
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)
        # WHEN
        await media_item_use_case.list_(
            owner_id,
            only_favourites=True,
            offset=100,
            limit=50,
        )
        # THEN
        media_item_service.list_.assert_awaited_once_with(
            owner_id,
            only_favourites=True,
            offset=100,
            limit=50,
        )


class TestListCategories:
    async def test(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        owner_id, media_item_id = uuid.uuid7(), uuid.uuid7()
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)
        # WHEN
        result = await media_item_use_case.list_categories(owner_id, media_item_id)
        # THEN
        assert result == media_item_service.list_categories.return_value
        media_item_service.get_for_owner.assert_awaited_once_with(
            owner_id, media_item_id
        )
        item = media_item_service.get_for_owner.return_value
        media_item_service.list_categories.assert_awaited_once_with(item.id)


class TestListDeleted:
    async def test(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        owner_id = uuid.uuid7()
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)
        # WHEN
        result = await media_item_use_case.list_deleted(owner_id)
        # THEN
        assert result == media_item_service.list_deleted.return_value
        media_item_service.list_deleted.assert_awaited_once_with(
            owner_id, offset=0, limit=2_000
        )


class TestListFavouriteIDs:
    async def test(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        user_id = uuid.uuid7()
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)
        # WHEN
        result = await media_item_use_case.list_favourite_ids(user_id)
        # THEN
        assert result == media_item_service.list_favourite_ids.return_value
        media_item_service.list_favourite_ids.assert_awaited_once_with(user_id)


class TestMarkFavouriteBatch:
    async def test(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        user_id = uuid.uuid7()
        ids = [uuid.uuid7(), uuid.uuid7()]
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)
        # WHEN
        await media_item_use_case.mark_favourite_batch(user_id, ids)
        # THEN
        media_item_service.mark_favourite_batch.assert_awaited_once_with(user_id, ids)


class TestPurge:
    @staticmethod
    def _aiter_items_factory[T](
        batches: list[list[T]]
    ) -> Callable[[UUID], AsyncIterator[list[T]]]:
        async def _aiter_items(owner_id: UUID) -> AsyncIterator[list[T]]:
            for batch in batches:
                yield batch
        return _aiter_items

    async def test(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        owner_id = uuid.uuid7()
        items = [[_make_media_item(), _make_media_item()]]
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)

        media_item_service.iter_deleted = self._aiter_items_factory(items)
        ids = [item.id for item in items[0]]

        # WHEN
        await media_item_use_case.purge(owner_id)

        # THEN
        media_item_service.delete_permanently.assert_awaited_once_with(ids)


class TestRestoreBatch:
    async def test(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        owner_id = uuid.uuid7()
        ids = [uuid.uuid7(), uuid.uuid7()]
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)
        # WHEN
        result = await media_item_use_case.restore_batch(owner_id, ids)
        # THEN
        assert result == media_item_service.restore_batch.return_value
        media_item_service.restore_batch.assert_awaited_once_with(owner_id, ids)


class TestSetCategories:
    async def test(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        owner_id, media_item_id = uuid.uuid7(), uuid.uuid7()
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)
        categories = [MediaItem.Category.Name.ANIMALS, MediaItem.Category.Name.PETS]
        # WHEN
        await media_item_use_case.set_categories(
            owner_id, media_item_id, categories=categories
        )
        # THEN
        media_item_service.get_for_owner.assert_awaited_once_with(
            owner_id, media_item_id
        )
        item = media_item_service.get_for_owner.return_value
        media_item_service.set_categories.assert_awaited_once_with(
            item.id, categories
        )


class TestThumbnail:
    async def test(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        owner_id, media_item_id = uuid.uuid7(), uuid.uuid7()
        item = _make_media_item()
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)
        media_item_service.get_for_owner.return_value = item
        thumbnailer = cast(mock.MagicMock, media_item_use_case.thumbnailer)
        thumbnail = thumbnailer.thumbnail.return_value
        # WHEN
        result = await media_item_use_case.thumbnail(owner_id, media_item_id, size=72)
        # THEN
        assert result == (item, *thumbnail)
        media_item_service.get_for_owner.assert_awaited_once_with(
            owner_id, media_item_id
        )
        thumbnailer.thumbnail.assert_awaited_once_with(item.blob_id, item.chash, 72)


class TestUnmarkFavouriteBatch:
    async def test(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        user_id = uuid.uuid7()
        ids = [uuid.uuid7(), uuid.uuid7()]
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)
        # WHEN
        await media_item_use_case.unmark_favourite_batch(user_id, ids)
        # THEN
        media_item_service.unmark_favourite_batch.assert_awaited_once_with(user_id, ids)


class TestUpload:
    async def test(self, media_item_use_case: MediaItemUseCase):
        # GIVEN
        owner_id = uuid.uuid7()
        name = "photo.jpg"
        content = mock.MagicMock()
        media_type = MediaType.IMAGE_JPEG
        media_item_service = cast(mock.MagicMock, media_item_use_case.media_item)
        blob_processor = cast(mock.MagicMock, media_item_use_case.blob_processor)
        item = media_item_service.create.return_value
        # WHEN
        result = await media_item_use_case.upload(owner_id, name, content, media_type)
        # THEN
        assert result == item
        media_item_service.create.assert_awaited_once_with(
            owner_id, name, content, media_type
        )
        blob_processor.process_async.assert_awaited_once_with(item.blob_id)
