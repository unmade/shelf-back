from __future__ import annotations

import uuid
from typing import IO, TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.files.domain import ContentMetadata
from app.app.services.metadata import _Tracker

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.services import MetadataService

pytestmark = [pytest.mark.asyncio]


class TestGetByFileID:
    async def test(self, metadata_service: MetadataService):
        # GIVEN
        file_id = str(uuid.uuid4())
        db = cast(mock.MagicMock, metadata_service.db)
        # WHEN
        result = await metadata_service.get_by_file_id(file_id)
        # THEN
        assert result == db.metadata.get_by_file_id.return_value
        db.metadata.get_by_file_id.assert_awaited_once_with(file_id)


@mock.patch("app.metadata.load")
class TestTrack:
    async def test(
        self,
        load_metadata: MagicMock,
        metadata_service: MetadataService,
        image_content: IO[bytes],
    ):
        # GIVEN
        file_id = str(uuid.uuid4())
        db = cast(mock.MagicMock, metadata_service.db)
        # WHEN
        await metadata_service.track(file_id, image_content)
        # THEN
        load_metadata.assert_called_once_with(image_content, mediatype="image/jpeg")
        db.metadata.save.assert_awaited_once_with(
            ContentMetadata(file_id=file_id, data=load_metadata.return_value)
        )

    async def test_when_metadata_is_none(
        self,
        load_metadata: MagicMock,
        metadata_service: MetadataService,
        image_content: IO[bytes],
    ):
        # GIVEN
        file_id = str(uuid.uuid4())
        db = cast(mock.MagicMock, metadata_service.db)
        load_metadata.return_value = None
        # WHEN
        await metadata_service.track(file_id, image_content)
        # THEN
        load_metadata.assert_called_once_with(image_content, mediatype="image/jpeg")
        db.metadata.save.assert_not_awaited()


@mock.patch("app.metadata.load")
class TestTrackBatch:
    async def test(
        self,
        load_metadata: MagicMock,
        metadata_service: MetadataService,
        image_content: IO[bytes],
    ):
        # GIVEN
        file_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        db = cast(mock.MagicMock, metadata_service.db)
        # WHEN
        async with metadata_service.track_batch() as tracker:
            await tracker.add(file_ids[0], image_content)
            await tracker.add(file_ids[1], image_content)
        # THEN
        expected = _Tracker()
        expected._items = [
            ContentMetadata(file_id=file_ids[0], data=load_metadata.return_value),
            ContentMetadata(file_id=file_ids[1], data=load_metadata.return_value),
        ]
        db.metadata.save_batch.assert_awaited_once_with(expected)
