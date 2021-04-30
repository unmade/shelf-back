from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app import crud, errors

if TYPE_CHECKING:
    from app.typedefs import DBPool

pytestmark = [pytest.mark.asyncio]


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


async def test_get_account(db_pool: DBPool):
    username = "johndoe"
    await crud.user.create(db_pool, username, "psswd")
    await crud.account.create(db_pool, username)
    query = "SELECT User { id } FILTER .username=<str>$username"
    user = await db_pool.query_one(query, username=username)
    account = await crud.account.get(db_pool, user.id)
    assert account.username == username


async def test_list_all(db_pool: DBPool):
    usernames = ["user_a", "user_b"]
    for username in usernames:
        await crud.user.create(db_pool, username, "psswd")
        await crud.account.create(db_pool, username)
    accounts = await crud.account.list_all(db_pool, offset=0)
    assert accounts[0].username == "user_a"
    assert accounts[1].username == "user_b"
    assert len(accounts) == 2


async def test_list_all_limit_offset(db_pool: DBPool):
    usernames = ["user_a", "user_b"]
    for username in usernames:
        await crud.user.create(db_pool, username, "psswd")
        await crud.account.create(db_pool, username)
    accounts = await crud.account.list_all(db_pool, offset=1, limit=1)
    assert accounts[0].username == "user_b"
    assert len(accounts) == 1
