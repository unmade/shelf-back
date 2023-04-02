from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.app.users.usecases.user import AccountSpaceUsage

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.users.domain import Account, User
    from tests.api.conftest import TestClient

pytestmark = [pytest.mark.asyncio]


class TestGetCurrent:
    url = "/accounts/get_current"
    async def test(
        self,
        client: TestClient,
        user_use_case: MagicMock,
        account: Account,
        user: User,
    ):
        # GIVEN
        user_use_case.get_account.return_value = account
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        data = response.json()
        assert data["username"] == account.username
        assert data["email"] == account.email
        assert data["first_name"] == account.first_name
        assert data["last_name"] == account.last_name
        assert data["superuser"] is False
        assert response.status_code == 200


class TestGetSpaceUsage:
    url = "/accounts/get_space_usage"

    async def test(
        self,
        client: TestClient,
        user_use_case: MagicMock,
        user: User,
    ):
        # GIVEN
        space_usage = AccountSpaceUsage(used=256, quota=1024)
        user_use_case.get_account_space_usage.return_value = space_usage
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        assert response.json() == {"quota": space_usage.quota, "used": space_usage.used}
        assert response.status_code == 200
        user_use_case.get_account_space_usage.assert_awaited_once_with(user.id)
