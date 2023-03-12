from __future__ import annotations

import uuid
from typing import IO, TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.domain.entities import ContentMetadata

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.services import MetadataService

pytestmark = [pytest.mark.asyncio]


@mock.patch("app.metadata.load")
class TestTrack:
    async def test(
        self,
        load_metadata: MagicMock,
        metadata_service: MetadataService,
        image_content: IO[bytes],
    ):
        file_id = str(uuid.uuid4())
        load_metadata.return_value
        await metadata_service.track(file_id, image_content)
        load_metadata.assert_called_once_with(image_content, mediatype="image/jpeg")
        db = cast(mock.MagicMock, metadata_service.db)
        db.metadata.save.assert_awaited_once_with(
            ContentMetadata(file_id=file_id, data=load_metadata.return_value)
        )

    async def test_when_metadata_is_none(
        self,
        load_metadata: MagicMock,
        metadata_service: MetadataService,
        image_content: IO[bytes],
    ):
        file_id = str(uuid.uuid4())
        load_metadata.return_value = None
        await metadata_service.track(file_id, image_content)
        load_metadata.assert_called_once_with(image_content, mediatype="image/jpeg")
        db = cast(mock.MagicMock, metadata_service.db)
        db.metadata.save.assert_not_awaited()
