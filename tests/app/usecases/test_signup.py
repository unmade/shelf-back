from __future__ import annotations

from unittest import mock

import pytest

from app.app.services import NamespaceService, UserService
from app.app.usecases import SignUp

pytestmark = [pytest.mark.asyncio]


async def test_signup():
    user_service = mock.MagicMock(UserService)
    namespace_service = mock.MagicMock(NamespaceService)
    signup = SignUp(namespace_service=namespace_service, user_service=user_service)
    user = await signup("admin", "root", storage_quota=1024)
    user_service.create.assert_awaited_once_with("admin", "root", storage_quota=1024)
    namespace_service.create.assert_awaited_once_with(user.username, owner_id=user.id)
    assert user == user_service.create.return_value
