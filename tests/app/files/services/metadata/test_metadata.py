from __future__ import annotations

import uuid
from typing import IO, TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.files.domain import ContentMetadata, Exif

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.files.services import MetadataService

pytestmark = [pytest.mark.asyncio]


class TestGetByFileID:
    async def test(self, metadata_service: MetadataService):
        # GIVEN
        file_id = uuid.uuid4()
        db = cast(mock.MagicMock, metadata_service.db)
        # WHEN
        result = await metadata_service.get_by_file_id(file_id)
        # THEN
        assert result == db.metadata.get_by_file_id.return_value
        db.metadata.get_by_file_id.assert_awaited_once_with(file_id)


@mock.patch("app.app.files.services.metadata.readers.load")
class TestTrack:
    async def test(
        self,
        load_metadata: MagicMock,
        metadata_service: MetadataService,
        image_content: IO[bytes],
    ):
        # GIVEN
        file_id = uuid.uuid4()
        db = cast(mock.MagicMock, metadata_service.db)
        load_metadata.return_value = Exif(width=1280, height=800)
        # WHEN
        await metadata_service.track(file_id, image_content)
        # THEN
        load_metadata.assert_awaited_once_with(image_content)
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
        file_id = uuid.uuid4()
        db = cast(mock.MagicMock, metadata_service.db)
        load_metadata.return_value = None
        # WHEN
        await metadata_service.track(file_id, image_content)
        # THEN
        load_metadata.assert_awaited_once_with(image_content)
        db.metadata.save.assert_not_awaited()


@mock.patch("app.app.files.services.metadata.readers.load")
class TestTrackBatch:
    async def test(
        self,
        load_metadata: MagicMock,
        metadata_service: MetadataService,
        image_content: IO[bytes],
    ):
        # GIVEN
        file_ids = [uuid.uuid4() for _ in range(3)]
        db = cast(mock.MagicMock, metadata_service.db)
        load_metadata.side_effect = [
            Exif(width=1280, height=800),
            None,
            Exif(width=1440, height=900),
        ]
        # WHEN
        async with metadata_service.track_batch() as tracker:
            await tracker.add(file_ids[0], image_content)
            await tracker.add(file_ids[1], image_content)
            await tracker.add(file_ids[2], image_content)
        # THEN
        items = [
            ContentMetadata(file_id=file_ids[0], data=Exif(width=1280, height=800)),
            ContentMetadata(file_id=file_ids[2], data=Exif(width=1440, height=900)),
        ]
        db.metadata.save_batch.assert_awaited_once_with(items)
