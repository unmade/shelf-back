from __future__ import annotations

from unittest import mock

import pytest

from app.app.managers import SharingManager
from app.app.services import FileCoreService, SharingService


@pytest.fixture
def sharing_manager():
    """A mocked SharingManager instance."""
    return SharingManager(
        filecore=mock.MagicMock(spec=FileCoreService),
        sharing=mock.MagicMock(spec=SharingService),
    )
