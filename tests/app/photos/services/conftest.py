from __future__ import annotations

from unittest import mock

import pytest

from app.app.photos.repositories.media_item import IMediaItemRepository
from app.app.photos.services.media_item import MediaItemService


@pytest.fixture
def media_item_service():
    """A file service instance."""
    database = mock.MagicMock(
        media_item=mock.AsyncMock(IMediaItemRepository),
    )
    return MediaItemService(database=database)
