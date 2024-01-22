from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest import mock

import pytest
from pydantic_core import Url

from app.config import IndexerClientConfig
from app.infrastructure.clients import IndexerClient

if TYPE_CHECKING:
    from unittest.mock import MagicMock


pytestmark = [pytest.mark.anyio]


@pytest.fixture
async def indexer_cli():
    config = IndexerClientConfig(url=Url("http://localhost"))
    async with IndexerClient(config) as cli:
        yield cli


class TestTrack:
    @mock.patch("app.infrastructure.clients.indexer.AsyncClient.post")
    async def test(self, post_mock: MagicMock, indexer_cli: IndexerClient):
        # GIVEN
        file_id, storage_path = uuid.uuid4(), "ab/cd/ef/thumb_768.webp"
        # WHEN
        await indexer_cli.track(file_id, storage_path)
        # THEN
        post_mock.assert_awaited_once_with(
            "/api/photos/process",
            json={
                "file_id": str(file_id),
                "storage_path": storage_path
            }
        )
