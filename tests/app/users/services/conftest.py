from __future__ import annotations

from unittest import mock

import pytest

from app.app.users.repositories import (
    IAccountRepository,
    IBookmarkRepository,
    IUserRepository,
)
from app.app.users.services import BookmarkService, UserService


@pytest.fixture
def bookmark_service() -> BookmarkService:
    """A BookmarkService instance with mocked database."""
    database = mock.MagicMock(
        bookmark=mock.AsyncMock(IBookmarkRepository),
    )
    return BookmarkService(database=database)


@pytest.fixture
def user_service() -> UserService:
    """A UserService instance with mocked database."""
    database = mock.MagicMock(
        account=mock.AsyncMock(IAccountRepository),
        user=mock.AsyncMock(IUserRepository),
    )
    return UserService(database=database)
