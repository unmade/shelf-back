from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.api.exceptions import InvalidToken, MissingToken

if TYPE_CHECKING:
    from tests.conftest import TestClient

pytestmark = [pytest.mark.asyncio]


async def test_get_account_me(client: TestClient, user_factory):
    user = await user_factory()
    response = await client.login(user.id).get("/accounts/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == user.username
    assert data["namespace"]["path"] == user.username


async def test_get_account_me_but_token_is_missing(client: TestClient):
    response = await client.get("/accounts/me")
    assert response.status_code == 401
    assert response.json() == MissingToken().as_dict()


async def test_get_account_me_but_token_is_invalid(client: TestClient):
    headers = {"Authorization": "Bearer invalid-token"}
    response = await client.get("/accounts/me", headers=headers)
    assert response.status_code == 403
    assert response.json() == InvalidToken().as_dict()
