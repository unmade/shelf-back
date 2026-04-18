from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.worker.jobs import blobs

if TYPE_CHECKING:
    from app.worker.main import ARQContext

pytestmark = [pytest.mark.anyio]


class TestProcessBlobContent:
    async def test(self, arq_context: ARQContext):
        # GIVEN
        blob_id = uuid.uuid4()
        usecases = cast(mock.MagicMock, arq_context["usecases"])
        content_processor = usecases.blob_content_processor
        # WHEN
        await blobs.process_blob_content(arq_context, blob_id)
        # THEN
        content_processor.process.assert_awaited_once_with(blob_id)
