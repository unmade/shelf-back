from __future__ import annotations

from unittest import mock

import pytest

from app.app.files.services import NamespaceService, SharingService
from app.app.files.services.file import FileCoreService
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
def photos_use_case() -> MediaItemUseCase:
    """A mocked MediaItemUseCase instance."""
    services = mock.MagicMock(
        filecore=mock.MagicMock(spec=FileCoreService),
        media_item=mock.MagicMock(spec=MediaItemService),
        namespace=mock.MagicMock(spec=NamespaceService),
        sharing=mock.MagicMock(spec=SharingService),
    )
    return MediaItemUseCase(services=services)
