from __future__ import annotations

from typing import TYPE_CHECKING

from app.api.exceptions import UserNotFound

if TYPE_CHECKING:
    from ..conftest import TestClient


def test_get_tokens(client: TestClient, user_factory):
    user = user_factory()
    data = {
        "username": user.username,
        "password": "root",
    }
    response = client.post("/auth/tokens", data=data)
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_get_tokens_but_user_does_not_exists(client: TestClient):
    data = {
        "username": "username",
        "password": "root",
    }
    response = client.post("/auth/tokens", data=data)
    assert response.status_code == 404
    assert response.json() == UserNotFound().as_dict()


def test_get_tokens_but_password_is_invalid(client: TestClient, user_factory):
    user = user_factory()
    data = {
        "username": user.username,
        "password": "wrong password",
    }
    response = client.post("/auth/tokens", data=data)
    assert response.status_code == 404
    assert response.json() == UserNotFound().as_dict()


def test_refresh_token(client: TestClient, user_factory):
    user = user_factory()
    response = client.login(user.id).put("/auth/tokens")
    assert response.status_code == 200
    assert "access_token" in response.json()
