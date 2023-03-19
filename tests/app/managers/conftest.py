from __future__ import annotations

from unittest import mock

import pytest

from app.app.managers import NamespaceManager, SharingManager
from app.app.services import (
    DuplicateFinderService,
    FileCoreService,
    MetadataService,
    NamespaceService,
    SharingService,
    UserService,
)


@pytest.fixture
def ns_manager():
    """A mocked NamespaceManager instance."""
    return NamespaceManager(
        dupefinder=mock.MagicMock(spec=DuplicateFinderService),
        filecore=mock.MagicMock(spec=FileCoreService),
        metadata=mock.MagicMock(spec=MetadataService),
        namespace=mock.MagicMock(spec=NamespaceService),
        user=mock.MagicMock(spec=UserService),
    )


@pytest.fixture
def sharing_manager():
    """A mocked SharingManager instance."""
    return SharingManager(
        filecore=mock.MagicMock(spec=FileCoreService),
        sharing=mock.MagicMock(spec=SharingService),
    )
