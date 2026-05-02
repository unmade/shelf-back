from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app.app.blobs.repositories import IBlobMetadataRepository
from app.app.blobs.services import (
    BlobContentProcessor,
    BlobMetadataService,
    BlobService,
    BlobThumbnailService,
)
from app.app.infrastructure.storage import IStorage
from app.app.infrastructure.worker import IWorker

if TYPE_CHECKING:
    from typing import Protocol

    from app.app.blobs.domain import Blob, IBlobContent
    from app.infrastructure.database.tortoise import TortoiseDatabase

    class BlobFactory(Protocol):
        async def __call__(
            self,
            storage_key: str,
            content: IBlobContent,
            media_type: str = "text/plain",
        ) -> Blob:
            ...


@pytest.fixture
def blob_service(
    tortoise_database: TortoiseDatabase,
    fs_storage: IStorage,
) -> BlobService:
    """A BlobService instance with real database and storage."""
    worker = mock.AsyncMock(IWorker)
    return BlobService(database=tortoise_database, storage=fs_storage, worker=worker)


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
    blob_service = mock.MagicMock(BlobService)
    storage = mock.AsyncMock(IStorage)
    return BlobThumbnailService(
        blob_service=blob_service,
        storage=storage,
        max_file_size=10 * 1024 * 1024,
    )


@pytest.fixture
def blob_factory(blob_service: BlobService) -> BlobFactory:
    async def factory(
        storage_key: str,
        content: IBlobContent,
        media_type: str = "text/plain",
    ) -> Blob:
        return await blob_service.create(storage_key, content, media_type)

    return factory
