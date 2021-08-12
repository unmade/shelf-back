from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from app.api.accounts.exceptions import UserAlreadyExists

if TYPE_CHECKING:
    from app.entities import Account, User
    from tests.conftest import TestClient
    from tests.factories import AccountFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database(transaction=True)]


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
    client: TestClient,
    superuser: User,
    payload,
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


async def test_create_but_email_is_taken(
    client: TestClient,
    superuser: User,
    account_factory: AccountFactory,
) -> None:
    await account_factory(email="johndoe@example.com", user=superuser)
    payload = {
        "username": "johndoe",
        "password": "password",
        "email": "johndoe@example.com",
    }
    response = await client.login(superuser.id).post("/accounts/create", json=payload)
    message = "Email 'johndoe@example.com' is taken"
    assert response.json() == UserAlreadyExists(message).as_dict()
    assert response.status_code == 400


async def test_get_current(client: TestClient, account: Account):
    response = await client.login(account.user.id).get("/accounts/get_current")
    data = response.json()
    assert data["username"] == account.user.username
    assert data["email"] is not None
    assert data["first_name"] == ""
    assert data["last_name"] == ""
    assert data["superuser"] is False
    assert response.status_code == 200


async def test_list_all(
    client: TestClient,
    superuser: User,
    account_factory: AccountFactory,
):
    await account_factory(user=superuser)
    await asyncio.gather(
        *(account_factory() for _ in range(3))
    )
    client.login(superuser.id)
    response = await client.get("/accounts/list_all")
    data = response.json()
    assert data["page"] == 1
    assert data["count"] == 4
    assert len(data["results"]) == 4
    usernames = [result["username"] for result in data["results"]]
    assert usernames == sorted(usernames)


async def test_list_all_with_page_params(
    client: TestClient,
    superuser: User,
    account_factory: AccountFactory,
) -> None:
    await account_factory(user=superuser)
    await asyncio.gather(
        *(account_factory() for _ in range(7))
    )
    client.login(superuser.id)
    response = await client.get("/accounts/list_all?page=2&per_page=5")
    data = response.json()
    assert data["page"] == 2
    assert data["count"] == 8
    assert len(data["results"]) == 3
    usernames = [result["username"] for result in data["results"]]
    assert usernames == sorted(usernames)


async def test_update_account(client: TestClient, account: Account):
    payload = {"first_name": "John", "last_name": "Doe"}
    client.login(account.user.id)
    response = await client.patch("/accounts/update", json=payload)
    data = response.json()
    assert data["email"] is not None
    assert data["first_name"] == "John"
    assert data["last_name"] == "Doe"
    assert response.status_code == 200


async def test_update_account_unset_email(client: TestClient, account: Account):
    payload = {"email": None}
    client.login(account.user.id)
    response = await client.patch("/accounts/update", json=payload)
    data = response.json()
    assert data["email"] is None
    assert response.status_code == 200
