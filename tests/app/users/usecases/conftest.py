from __future__ import annotations

from contextlib import AsyncExitStack
from unittest import mock

import pytest

from app.app.files.services import FileService, NamespaceService
from app.app.users.services import BookmarkService, UserService
from app.app.users.usecases import UserUseCase


async def _atomic():
    yield AsyncExitStack()


@pytest.fixture
def user_use_case():
    services = mock.MagicMock(
        bookmark=mock.MagicMock(BookmarkService),
        file=mock.MagicMock(FileService),
        namespace=mock.MagicMock(NamespaceService),
        user=mock.MagicMock(UserService),
        atomic=_atomic,
    )
    return UserUseCase(services=services)
