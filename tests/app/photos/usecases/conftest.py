from __future__ import annotations

from unittest import mock

import pytest

from app.app.files.services import NamespaceService, SharingService
from app.app.photos.services import MediaItemService
from app.app.photos.usecases import PhotosUseCase


@pytest.fixture
def photos_use_case():
    """A mocked PhotosUseCase instance."""
    services = mock.MagicMock(
        media_item=mock.MagicMock(spec=MediaItemService),
        namespace=mock.MagicMock(spec=NamespaceService),
        sharing=mock.MagicMock(spec=SharingService),
    )
    return PhotosUseCase(services=services)
