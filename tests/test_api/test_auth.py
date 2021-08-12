from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.api.auth.exceptions import InvalidCredentials

if TYPE_CHECKING:
    from app.entities import User
    from tests.conftest import TestClient
    from tests.factories import UserFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database(transaction=True)]


async def test_get_tokens(client: TestClient, user_factory: UserFactory):
    user = await user_factory(hash_password=True)
    data = {
        "username": user.username,
        "password": "root",
    }
    response = await client.post("/auth/tokens", data=data)
    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_get_tokens_but_user_does_not_exists(client: TestClient):
    data = {
        "username": "username",
        "password": "root",
    }
    response = await client.post("/auth/tokens", data=data)
    assert response.status_code == 401
    assert response.json() == InvalidCredentials().as_dict()


async def test_get_tokens_but_password_is_invalid(
    client: TestClient,
    user_factory: UserFactory,
):
    user = await user_factory(hash_password=True)
    data = {
        "username": user.username,
        "password": "wrong password",
    }
    response = await client.post("/auth/tokens", data=data)
    assert response.status_code == 401
    assert response.json() == InvalidCredentials().as_dict()


async def test_refresh_token(client: TestClient, user: User):
    response = await client.login(user.id).put("/auth/tokens")
    assert response.status_code == 200
    assert "access_token" in response.json()
