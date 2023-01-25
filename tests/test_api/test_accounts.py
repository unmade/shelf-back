from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app.domain.entities import Account

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from fastapi import FastAPI

    from app.entities import User
    from tests.conftest import TestClient

pytestmark = [pytest.mark.asyncio, pytest.mark.database(transaction=True)]


@pytest.fixture
def ns_service(app: FastAPI):
    service = app.state.provider.service
    service_mock = mock.MagicMock(service.namespace)
    with mock.patch.object(service, "namespace", service_mock) as mocked:
        yield mocked


@pytest.fixture
def user_service(app: FastAPI):
    service = app.state.provider.service
    service_mock = mock.MagicMock(service.user)
    with mock.patch.object(service, "user", service_mock) as mocked:
        yield mocked


class TestGetCurrent:
    async def test(
        self,
        client: TestClient,
        account: Account,
        user: User,
        user_service: MagicMock,
    ):
        user_service.get_account.return_value = account
        response = await client.login(user.id).get("/accounts/get_current")
        data = response.json()
        assert data["username"] == account.username
        assert data["email"] == account.email
        assert data["first_name"] == account.first_name
        assert data["last_name"] == account.last_name
        assert data["superuser"] is False
        assert response.status_code == 200


class TestGetSpaceUsage:
    async def test(
        self,
        client: TestClient,
        account: Account,
        user: User,
        ns_service: MagicMock,
        user_service: MagicMock,
    ):
        user_id = str(user.id)
        user_service.get_account.return_value = account
        ns_service.get_space_used_by_owner_id.return_value = 256
        response = await client.login(user_id).get("/accounts/get_space_usage")
        assert response.json() == {"quota": account.storage_quota, "used": 256}
        assert response.status_code == 200
        user_service.get_account.assert_awaited_once_with(user_id)
        ns_service.get_space_used_by_owner_id.assert_awaited_once_with(user_id)
