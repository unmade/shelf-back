from __future__ import annotations

from typing import TYPE_CHECKING

from app.api.exceptions import InvalidToken, MissingToken

if TYPE_CHECKING:
    from ..conftest import TestClient


def test_get_account_me(client: TestClient, user_factory):
    user = user_factory()
    response = client.login(user.id).get("/accounts/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == user.username
    assert data["namespace"]["path"] == user.username


def test_get_account_me_but_token_is_missing(client: TestClient):
    response = client.get("/accounts/me")
    assert response.status_code == 401
    assert response.json() == MissingToken().as_dict()


def test_get_account_me_but_token_is_invalid(client: TestClient):
    headers = {"Authorization": "Bearer invalid-token"}
    response = client.get("/accounts/me", headers=headers)
    assert response.status_code == 403
    assert response.json() == InvalidToken().as_dict()
