from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.api.accounts.exceptions import UserAlreadyExists

if TYPE_CHECKING:
    from app.entities import User
    from tests.conftest import TestClient

pytestmark = [pytest.mark.asyncio]


async def test_create(client: TestClient, user: User):
    payload = {
        "username": "johndoe",
        "password": "psswd",
        "last_name": "Doe",
    }
    response = await client.login(user.id).post("/accounts/create", json=payload)
    data = response.json()
    assert data["username"] == payload["username"]
    assert data["email"] is None
    assert data["first_name"] == ""
    assert data["last_name"] == "Doe"
    assert response.status_code == 200


async def test_create_but_username_is_taken(client: TestClient, user: User):
    payload = {
        "username": user.username,
        "password": "psswd"
    }
    response = await client.login(user.id).post("/accounts/create", json=payload)
    message = f"Username '{user.username}' is taken"
    assert response.json() == UserAlreadyExists(message).as_dict()
    assert response.status_code == 400


async def test_create_but_email_is_taken(client: TestClient, user_factory):
    user = await user_factory(email="johndoe@example.com")
    payload = {
        "username": "johndoe",
        "password": "psswd",
        "email": "johndoe@example.com",
    }
    response = await client.login(user.id).post("/accounts/create", json=payload)
    message = "Email 'johndoe@example.com' is taken"
    assert response.json() == UserAlreadyExists(message).as_dict()
    assert response.status_code == 400


async def test_get_current(client: TestClient, user: User):
    response = await client.login(user.id).get("/accounts/get_current")
    data = response.json()
    assert data["username"] == user.username
    assert data["email"] is None
    assert data["first_name"] == ""
    assert data["last_name"] == ""
    assert response.status_code == 200
