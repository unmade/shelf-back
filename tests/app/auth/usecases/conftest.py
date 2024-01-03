from __future__ import annotations

from contextlib import AsyncExitStack
from unittest import mock

import pytest

from app.app.audit.services import AuditTrailService
from app.app.auth.services import TokenService
from app.app.auth.usecases import AuthUseCase
from app.app.files.services import NamespaceService
from app.app.users.services import UserService


async def _atomic():
    yield AsyncExitStack()


@pytest.fixture
def auth_use_case():
    """An AuthUseCase instance with mocked services."""
    services = mock.MagicMock(
        audit_trail=mock.MagicMock(AuditTrailService),
        namespace=mock.MagicMock(NamespaceService),
        token=mock.MagicMock(TokenService),
        user=mock.MagicMock(UserService),
        atomic=_atomic,
    )
    return AuthUseCase(services=services)
