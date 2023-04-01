from __future__ import annotations

from unittest import mock

import pytest

from app.app.files.services import FileCoreService, NamespaceService
from app.app.users.services import BookmarkService, UserService
from app.app.users.usecases import UserUseCase


@pytest.fixture
def user_use_case():
    return UserUseCase(
        bookmark_service=mock.MagicMock(BookmarkService),
        filecore=mock.MagicMock(FileCoreService),
        namespace_service=mock.MagicMock(NamespaceService),
        user_service=mock.MagicMock(UserService),
    )
