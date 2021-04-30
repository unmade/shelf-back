from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app import crud, errors

if TYPE_CHECKING:
    from app.typedefs import DBPool
    from app.crud.account import AccountUpdate

pytestmark = [pytest.mark.asyncio]


@pytest.fixture(name="account_factory")
def _account_factory(db_pool):
    """Create User and Account in the database."""
    async def make_account(
        username, password="root", *, email=None, first_name="", last_name=""
    ):
        with mock.patch("app.security.make_password", return_value=password):
            await crud.user.create(db_pool, username, password)
        query = "SELECT User { id } FILTER .username=<str>$username"
        user, account = await asyncio.gather(
            db_pool.query_one(query, username=username),
            crud.account.create(
                db_pool,
                username,
                email=email,
                first_name=first_name,
                last_name=last_name,
            )
        )
        return user.id, account
    return make_account


async def test_create_account(db_pool: DBPool):
    await crud.user.create(db_pool, "johndoe", "psswd")
    await crud.account.create(db_pool, "johndoe", first_name="John")

    account = await db_pool.query_one("""
        SELECT Account {
            email,
            first_name,
            last_name
        }
        FILTER
            .user.username = <str>$username
        LIMIT 1
    """, username="johndoe")

    assert account.email is None
    assert account.first_name == "John"
    assert account.last_name == ""


async def test_create_account_but_email_is_taken(db_pool: DBPool):
    await crud.user.create(db_pool, "user_a", "pssw")
    await crud.user.create(db_pool, "user_b", "pssw")
    await crud.account.create(db_pool, "user_a", email="user@example.com")

    with pytest.raises(errors.UserAlreadyExists) as excinfo:
        await crud.account.create(db_pool, "user_b", email="user@example.com")

    assert str(excinfo.value) == "Email 'user@example.com' is taken"


async def test_get_account(db_pool: DBPool, account_factory):
    username = "johndoe"
    user_id, _ = await account_factory(username)
    account = await crud.account.get(db_pool, user_id)
    assert account.username == username


async def test_get_account_but_user_not_found(db_pool: DBPool):
    user_id = uuid.uuid4()
    with pytest.raises(errors.UserNotFound) as excinfo:
        await crud.account.get(db_pool, user_id)

    assert str(excinfo.value) == f"No account for user with id: {user_id}"


async def test_list_all(db_pool: DBPool, account_factory):
    usernames = ["user_a", "user_b"]
    await asyncio.gather(*(
        account_factory(username) for username in usernames
    ))
    accounts = await crud.account.list_all(db_pool, offset=0)
    assert accounts[0].username == "user_a"
    assert accounts[1].username == "user_b"
    assert len(accounts) == 2


async def test_list_all_limit_offset(db_pool: DBPool, account_factory):
    usernames = ["user_a", "user_b"]
    await asyncio.gather(*(
        account_factory(username) for username in usernames
    ))
    accounts = await crud.account.list_all(db_pool, offset=1, limit=1)
    assert accounts[0].username == "user_b"
    assert len(accounts) == 1


async def test_update_account(db_pool: DBPool, account_factory):
    user_id, _ = await account_factory("johndoe")
    to_update: AccountUpdate = {"email": "johndoe@example.com"}
    account = await crud.account.update(db_pool, user_id, to_update)
    assert account.email == "johndoe@example.com"
    account = await crud.account.get(db_pool, user_id)
    assert account.email == "johndoe@example.com"
