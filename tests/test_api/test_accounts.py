from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.api.accounts.exceptions import UserAlreadyExists

if TYPE_CHECKING:
    from app.entities import User
    from tests.conftest import TestClient

pytestmark = [pytest.mark.asyncio]


async def test_create(client: TestClient, superuser: User):
    payload = {
        "username": "johndoe",
        "password": "password",
        "last_name": "Doe",
    }
    response = await client.login(superuser.id).post("/accounts/create", json=payload)
    data = response.json()
    assert data["username"] == payload["username"]
    assert data["email"] is None
    assert data["first_name"] == ""
    assert data["last_name"] == "Doe"
    assert response.status_code == 200


@pytest.mark.parametrize("payload", [
    {
        "username": "jd",  # too short
        "password": "password",
    },
    {
        "username": "johndoe",
        "password": "psswrd",  # too short
    },
    {
        "username": "johndoe",
        # password is missing
    },
    {
        "username": "johndoe",
        "password": "password",
        "email": "johndoe.com",  # invalid email
    },
])
async def test_create_but_payload_is_invalid(
    client: TestClient, superuser: User, payload,
):
    response = await client.login(superuser.id).post("/accounts/create", json=payload)
    assert response.status_code == 422


async def test_create_but_username_is_taken(client: TestClient, superuser: User):
    payload = {
        "username": superuser.username,
        "password": "password",
    }
    response = await client.login(superuser.id).post("/accounts/create", json=payload)
    message = f"Username '{superuser.username}' is taken"
    assert response.json() == UserAlreadyExists(message).as_dict()
    assert response.status_code == 400


async def test_create_but_email_is_taken(client: TestClient, user_factory):
    superuser: User = await user_factory(email="johndoe@example.com", superuser=True)
    payload = {
        "username": "johndoe",
        "password": "password",
        "email": "johndoe@example.com",
    }
    response = await client.login(superuser.id).post("/accounts/create", json=payload)
    message = "Email 'johndoe@example.com' is taken"
    assert response.json() == UserAlreadyExists(message).as_dict()
    assert response.status_code == 400


async def test_get_current(client: TestClient, user_factory):
    user: User = await user_factory()
    response = await client.login(user.id).get("/accounts/get_current")
    data = response.json()
    assert data["username"] == user.username
    assert data["email"] is None
    assert data["first_name"] == ""
    assert data["last_name"] == ""
    assert response.status_code == 200
