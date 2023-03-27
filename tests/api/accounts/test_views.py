from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

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
        account: Account,
        user: User,
        user_service: MagicMock,
    ):
        # GIVEN
        user_service.get_account.return_value = account
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
        account: Account,
        user: User,
        ns_service: MagicMock,
        user_service: MagicMock,
    ):
        # GIVEN
        user_service.get_account.return_value = account
        ns_service.get_space_used_by_owner_id.return_value = 256
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        assert response.json() == {"quota": account.storage_quota, "used": 256}
        assert response.status_code == 200
        user_service.get_account.assert_awaited_once_with(user.id)
        ns_service.get_space_used_by_owner_id.assert_awaited_once_with(user.id)
