from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.blobs.domain import BlobMetadata
from app.toolkit.metadata import Exif

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.blobs.domain import IBlobContent
    from app.app.blobs.services import BlobMetadataService

pytestmark = [pytest.mark.anyio]


class TestGetByBlobID:
    async def test(self, blob_metadata_service: BlobMetadataService):
        # GIVEN
        file_id = uuid.uuid4()
        db = cast(mock.MagicMock, blob_metadata_service.db)
        # WHEN
        result = await blob_metadata_service.get_by_blob_id(file_id)
        # THEN
        assert result == db.blob_metadata.get_by_blob_id.return_value
        db.blob_metadata.get_by_blob_id.assert_awaited_once_with(file_id)


@mock.patch("app.app.blobs.services.metadata.metadata.metadata.load")
class TestTrack:
    async def test(
        self,
        load_metadata: MagicMock,
        blob_metadata_service: BlobMetadataService,
        image_content: IBlobContent,
    ):
        # GIVEN
        file_id = uuid.uuid4()
        db = cast(mock.MagicMock, blob_metadata_service.db)
        load_metadata.return_value = Exif(width=1280, height=800)
        # WHEN
        await blob_metadata_service.track(file_id, image_content.file)
        # THEN
        load_metadata.assert_awaited_once_with(image_content.file)
        db.blob_metadata.save.assert_awaited_once_with(
            BlobMetadata(blob_id=file_id, data=load_metadata.return_value)
        )

    async def test_when_metadata_is_none(
        self,
        load_metadata: MagicMock,
        blob_metadata_service: BlobMetadataService,
        image_content: IBlobContent,
    ):
        # GIVEN
        file_id = uuid.uuid4()
        db = cast(mock.MagicMock, blob_metadata_service.db)
        load_metadata.return_value = None
        # WHEN
        await blob_metadata_service.track(file_id, image_content.file)
        # THEN
        load_metadata.assert_awaited_once_with(image_content.file)
        db.blob_metadata.save.assert_not_awaited()
