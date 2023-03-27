from __future__ import annotations

from unittest import mock

import pytest

from app.app.auth.services import TokenService
from app.app.auth.usecases.auth import AuthUseCase
from app.app.files.services import NamespaceService
from app.app.users.services import UserService


@pytest.fixture
def auth_use_case():
    """An AuthUseCase instance with mocked services."""
    return AuthUseCase(
        namespace_service=mock.MagicMock(NamespaceService),
        token_service=mock.MagicMock(TokenService),
        user_service=mock.MagicMock(UserService),
    )
