from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast
from unittest import mock

import freezegun
import pytest

from app.app.blobs.domain import Blob
from app.app.infrastructure.database import SENTINEL_ID
from app.app.infrastructure.storage import DownloadBatchItem
from app.toolkit import chash

if TYPE_CHECKING:
    from app.app.blobs.domain import IBlobContent
    from app.app.blobs.services import BlobService

pytestmark = [pytest.mark.anyio]


class TestCreate:
    async def test(
        self,
        blob_service: BlobService,
        content: IBlobContent,
    ):
        # GIVEN
        storage_key = "blobs/abc123"
        media_type = "image/jpeg"
        created_at = datetime(2026, 4, 19, 10, 11, 12, tzinfo=UTC)
        db = cast(mock.MagicMock, blob_service.db)
        storage = cast(mock.AsyncMock, blob_service.storage)
        storage_file = storage.save.return_value

        # WHEN
        with freezegun.freeze_time(created_at, real_asyncio=True):
            result = await blob_service.create(storage_key, content, media_type)

        # THEN
        assert result == db.blob.save.return_value
        storage.save.assert_awaited_once_with(storage_key, content)
        db.blob.save.assert_awaited_once_with(
            Blob(
                id=SENTINEL_ID,
                storage_key=storage_key,
                size=storage_file.size,
                chash=chash.chash(content.file),
                media_type=media_type,
                created_at=created_at,
            )
        )


class TestDelete:
    async def test(self, blob_service: BlobService):
        # GIVEN
        blob_id = uuid.uuid4()
        db = cast(mock.AsyncMock, blob_service.db)
        storage = cast(mock.AsyncMock, blob_service.storage)
        blob = db.blob.get_by_id.return_value
        # WHEN
        await blob_service.delete(blob_id)
        # THEN
        db.blob.get_by_id.assert_awaited_once_with(blob_id)
        storage.delete.assert_awaited_once_with(blob.storage_key)
        db.blob.delete.assert_awaited_once_with(blob_id)


class TestDeleteBatch:
    async def test(self, blob_service: BlobService):
        # GIVEN
        blob_ids = [uuid.uuid4(), uuid.uuid4()]
        db = cast(mock.AsyncMock, blob_service.db)
        storage = cast(mock.AsyncMock, blob_service.storage)
        blob_a = mock.MagicMock(storage_key="key_a")
        blob_b = mock.MagicMock(storage_key="key_b")
        db.blob.get_by_id_batch.return_value = [blob_a, blob_b]
        # WHEN
        await blob_service.delete_batch(blob_ids)
        # THEN
        db.blob.get_by_id_batch.assert_awaited_once_with(blob_ids)
        storage.delete_batch.assert_awaited_once_with(["key_a", "key_b"])
        db.blob.delete_batch.assert_awaited_once_with(blob_ids)


class TestDownload:
    def test(self, blob_service: BlobService):
        # GIVEN
        storage_key = "blobs/abc123"
        storage = cast(mock.MagicMock, blob_service.storage)
        # WHEN
        result = blob_service.download(storage_key)
        # THEN
        assert result == storage.download.return_value
        storage.download.assert_called_once_with(storage_key)


class TestDownloadBatch:
    def test(self, blob_service: BlobService):
        # GIVEN
        items = [
            DownloadBatchItem(key="blobs/a.jpg", is_dir=False, archive_path="a.jpg"),
            DownloadBatchItem(key="blobs/b.png", is_dir=False, archive_path="b.png"),
        ]
        storage = cast(mock.MagicMock, blob_service.storage)
        # WHEN
        result = blob_service.download_batch(items)
        # THEN
        assert result == storage.download_batch.return_value
        storage.download_batch.assert_called_once_with(items)


class TestGetById:
    async def test(self, blob_service: BlobService):
        # GIVEN
        blob_id = uuid.uuid4()
        db = cast(mock.AsyncMock, blob_service.db)
        # WHEN
        result = await blob_service.get_by_id(blob_id)
        # THEN
        assert result == db.blob.get_by_id.return_value
        db.blob.get_by_id.assert_awaited_once_with(blob_id)


class TestGetByIdBatch:
    async def test(self, blob_service: BlobService):
        # GIVEN
        blob_ids = [uuid.uuid7(), uuid.uuid7()]
        db = cast(mock.AsyncMock, blob_service.db)
        # WHEN
        result = await blob_service.get_by_id_batch(blob_ids)
        # THEN
        assert result == db.blob.get_by_id_batch.return_value
        db.blob.get_by_id_batch.assert_awaited_once_with(blob_ids)
