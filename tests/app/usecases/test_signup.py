from __future__ import annotations

from unittest import mock

import pytest

from app.app.managers import NamespaceManager
from app.app.usecases import SignUp
from app.app.users.services import UserService

pytestmark = [pytest.mark.asyncio]


async def test_signup():
    user_service = mock.MagicMock(UserService)
    ns_manager = mock.MagicMock(NamespaceManager)
    signup = SignUp(ns_manager=ns_manager, user_service=user_service)
    user = await signup("admin", "root", storage_quota=1024)
    user_service.create.assert_awaited_once_with("admin", "root", storage_quota=1024)
    ns_manager.create_namespace.assert_awaited_once_with(
        user.username, owner_id=user.id
    )
    assert user == user_service.create.return_value
