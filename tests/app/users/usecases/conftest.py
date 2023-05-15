from __future__ import annotations

from unittest import mock

import pytest

from app.app.files.services import FileService, NamespaceService
from app.app.users.services import BookmarkService, UserService
from app.app.users.usecases import UserUseCase


@pytest.fixture
def user_use_case():
    return UserUseCase(
        bookmark_service=mock.MagicMock(BookmarkService),
        file_service=mock.MagicMock(FileService),
        namespace_service=mock.MagicMock(NamespaceService),
        user_service=mock.MagicMock(UserService),
    )
