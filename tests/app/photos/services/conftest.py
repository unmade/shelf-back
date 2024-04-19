from __future__ import annotations

from unittest import mock

import pytest

from app.app.photos.repositories import IAlbumRepository, IMediaItemRepository
from app.app.photos.services import AlbumService, MediaItemService


@pytest.fixture
def album_service() -> AlbumService:
    """An AlbumService instance."""
    database = mock.MagicMock(
        album=mock.AsyncMock(IAlbumRepository),
    )
    return AlbumService(database=database)



@pytest.fixture
def media_item_service() -> MediaItemService:
    """A MediaItemService instance."""
    database = mock.MagicMock(
        media_item=mock.AsyncMock(IMediaItemRepository),
    )
    return MediaItemService(database=database)
