from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app.api.auth.exceptions import (
    InvalidCredentials,
    SignUpDisabled,
    UserAlreadyExists,
)

if TYPE_CHECKING:
    from app.entities import User
    from tests.conftest import TestClient
    from tests.factories import AccountFactory, UserFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database(transaction=True)]


@pytest.mark.parametrize("username", ["johndoe", "JohnDoe", " johndoe "])
async def test_sign_in(client: TestClient, user_factory: UserFactory, username: str):
    await user_factory(username="johndoe", hash_password=True)
    data = {
        "username": username,
        "password": "root",
    }
    response = await client.post("/auth/sign_in", data=data)
    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_sign_in_but_user_does_not_exists(client: TestClient):
    data = {
        "username": "username",
        "password": "root",
    }
    response = await client.post("/auth/sign_in", data=data)
    assert response.status_code == 401
    assert response.json() == InvalidCredentials().as_dict()


async def test_sign_in_but_password_is_invalid(
    client: TestClient,
    user_factory: UserFactory,
):
    user = await user_factory(hash_password=True)
    data = {
        "username": user.username,
        "password": "wrong password",
    }
    response = await client.post("/auth/sign_in", data=data)
    assert response.status_code == 401
    assert response.json() == InvalidCredentials().as_dict()


async def test_sign_up(client: TestClient):
    payload = {
        "username": "johndoe",
        "password": "Password1",
        "confirm_password": "Password1",
    }
    response = await client.post("/auth/sign_up", json=payload)
    assert "access_token" in response.json()
    assert response.status_code == 200


async def test_sign_up_but_it_is_disabled(client: TestClient):
    payload = {
        "username": "johndoe",
        "password": "Password1",
        "confirm_password": "Password1",
    }

    with mock.patch("app.config.FEATURES_SIGN_UP_DISABLED", True):
        response = await client.post("/auth/sign_up", json=payload)

    assert response.json() == SignUpDisabled().as_dict()
    assert response.status_code == 400


async def test_sign_up_but_payload_is_invalid(client: TestClient):
    payload = {
        "username": "jd",
        "password": "psswrd",
        "confirm_password": "Password1",
    }
    response = await client.post("/auth/sign_up", json=payload)
    assert response.status_code == 422


async def test_sign_up_but_username_is_taken(client: TestClient, superuser: User):
    payload = {
        "username": superuser.username,
        "password": "Password1",
        "confirm_password": "Password1",
    }
    response = await client.post("/auth/sign_up", json=payload)
    message = f"Username '{superuser.username}' is taken"
    assert response.json() == UserAlreadyExists(message).as_dict()
    assert response.status_code == 400


async def test_sign_up_but_email_is_taken(
    client: TestClient,
    superuser: User,
    account_factory: AccountFactory,
) -> None:
    await account_factory(email="johndoe@example.com", user=superuser)
    payload = {
        "username": "johndoe",
        "password": "Password1",
        "confirm_password": "Password1",
        "email": "johndoe@example.com",
    }
    response = await client.post("/auth/sign_up", json=payload)
    message = "Email 'johndoe@example.com' is taken"
    assert response.json() == UserAlreadyExists(message).as_dict()
    assert response.status_code == 400


async def test_refresh_token(client: TestClient, user: User):
    response = await client.login(user.id).post("/auth/refresh_token")
    assert response.status_code == 200
    assert "access_token" in response.json()
