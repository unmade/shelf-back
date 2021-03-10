from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.api.auth.exceptions import InvalidCredentials
from app.api.exceptions import InvalidToken, MissingToken

if TYPE_CHECKING:
    from app.entities import User
    from tests.conftest import TestClient

pytestmark = [pytest.mark.asyncio]


async def test_get_me(client: TestClient, user: User):
    response = await client.login(user.id).get("/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == user.username
    assert data["namespace"]["path"] == user.username


async def test_get_me_but_token_is_missing(client: TestClient):
    response = await client.get("/auth/me")
    assert response.status_code == 401
    assert response.json() == MissingToken().as_dict()


async def test_get_me_but_token_is_invalid(client: TestClient):
    headers = {"Authorization": "Bearer invalid-token"}
    response = await client.get("/auth/me", headers=headers)
    assert response.status_code == 403
    assert response.json() == InvalidToken().as_dict()


async def test_get_tokens(client: TestClient, user_factory):
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


async def test_get_tokens_but_password_is_invalid(client: TestClient, user_factory):
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
