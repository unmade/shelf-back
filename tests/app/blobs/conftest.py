from __future__ import annotations

from unittest import mock

import pytest

from app.app.blobs.repositories import IBlobRepository
from app.app.blobs.services import BlobService
from app.app.infrastructure.storage import IStorage


@pytest.fixture
def blob_service() -> BlobService:
    """A BlobService instance."""
    database = mock.MagicMock(
        blob=mock.AsyncMock(IBlobRepository),
    )
    storage = mock.AsyncMock(IStorage)
    return BlobService(database=database, storage=storage)
