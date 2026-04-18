from __future__ import annotations

import uuid
from typing import IO, TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.blobs.domain import Blob
from app.toolkit import timezone

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.app.blobs.domain import IBlobContent
    from app.app.blobs.services.content_processor import BlobContentProcessor

pytestmark = [pytest.mark.anyio]


async def _aiter(content: IO[bytes]) -> AsyncIterator[bytes]:
    for chunk in content:
        yield chunk


def _make_blob() -> Blob:
    return Blob(
        id=uuid.uuid7(),
        storage_key=f"{uuid.uuid4().hex}/{uuid.uuid4().hex}",
        chash=uuid.uuid4().hex,
        size=10,
        media_type="image/jpeg",
        created_at=timezone.now(),
    )


class TestProcess:
    async def test(
        self,
        content_processor: BlobContentProcessor,
        content: IBlobContent
    ):
        # GIVEN
        blob = _make_blob()
        blob_service = cast(mock.MagicMock, content_processor.blob_service)
        metadata_service = cast(mock.MagicMock, content_processor.metadata_service)
        thumbnail_service = cast(mock.MagicMock, content_processor.thumbnail_service)

        blob_service.get_by_id.return_value = blob
        blob_service.download.return_value = _aiter(content.file)

        # WHEN
        await content_processor.process(blob.id)

        # THEN
        blob_service.get_by_id.assert_awaited_once_with(blob.id)
        blob_service.download.assert_called_once_with(blob.storage_key)
        thumbnail_service.generate.assert_awaited_once()
        metadata_service.track.assert_awaited_once()


class TestProcessAsync:
    async def test(self, content_processor: BlobContentProcessor):
        # GIVEN
        blob_id = uuid.uuid7()
        worker = cast(mock.AsyncMock, content_processor.worker)
        # WHEN
        await content_processor.process_async(blob_id)
        # THEN
        worker.enqueue.assert_awaited_once_with(
            "process_blob_content", blob_id=blob_id,
        )
