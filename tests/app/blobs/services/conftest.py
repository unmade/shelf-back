from __future__ import annotations

from unittest import mock

import pytest

from app.app.blobs.repositories import IBlobMetadataRepository, IBlobRepository
from app.app.blobs.services import (
    BlobContentProcessor,
    BlobMetadataService,
    BlobService,
    BlobThumbnailService,
)
from app.app.infrastructure.storage import IStorage
from app.app.infrastructure.worker import IWorker


@pytest.fixture
def blob_service() -> BlobService:
    """A BlobService instance."""
    database = mock.MagicMock(
        blob=mock.AsyncMock(IBlobRepository),
    )
    storage = mock.AsyncMock(IStorage)
    return BlobService(database=database, storage=storage)


@pytest.fixture
def content_processor() -> BlobContentProcessor:
    return BlobContentProcessor(
        blob_service=mock.MagicMock(BlobService),
        metadata_service=mock.MagicMock(BlobMetadataService),
        thumbnail_service=mock.MagicMock(BlobThumbnailService),
        worker=mock.AsyncMock(IWorker),
    )


@pytest.fixture
def blob_metadata_service() -> BlobMetadataService:
    """A BlobMetadataService instance."""
    database = mock.MagicMock(
        blob_metadata=mock.AsyncMock(IBlobMetadataRepository),
    )
    return BlobMetadataService(database=database)


@pytest.fixture
def thumbnailer() -> BlobThumbnailService:
    """A BlobThumbnailService instance."""
    storage = mock.AsyncMock(IStorage)
    return BlobThumbnailService(storage=storage, max_file_size=10 * 1024 * 1024)
