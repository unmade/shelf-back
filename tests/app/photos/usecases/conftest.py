from __future__ import annotations

from unittest import mock

import pytest

from app.app.blobs.services import (
    BlobContentProcessor,
    BlobMetadataService,
    BlobThumbnailService,
)
from app.app.photos.services import AlbumService, MediaItemService
from app.app.photos.usecases import AlbumUseCase, MediaItemUseCase


@pytest.fixture
def album_use_case() -> AlbumUseCase:
    """A mocked AlbumUseCase instance."""
    services = mock.MagicMock(
        album=mock.MagicMock(spec=AlbumService),
    )
    return AlbumUseCase(services=services)


@pytest.fixture
def media_item_use_case() -> MediaItemUseCase:
    """A mocked MediaItemUseCase instance."""
    services = mock.MagicMock(
        blob_metadata=mock.MagicMock(spec=BlobMetadataService),
        blob_thumbnailer=mock.MagicMock(spec=BlobThumbnailService),
        blob_processor=mock.MagicMock(spec=BlobContentProcessor),
        media_item=mock.MagicMock(spec=MediaItemService),
    )
    return MediaItemUseCase(services=services)
