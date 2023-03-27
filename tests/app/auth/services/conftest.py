from __future__ import annotations

from unittest import mock

import pytest

from app.app.auth.repositories.token import ITokenRepository
from app.app.auth.services import TokenService


@pytest.fixture
def token_service():
    """A TokenService instance."""
    token_repo = mock.AsyncMock(ITokenRepository)
    return TokenService(token_repo=token_repo)
