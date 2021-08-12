from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

import pytest

from app import crud, errors

if TYPE_CHECKING:
    from app.typedefs import DBPool
    from app.entities import Account
    from app.crud.account import AccountUpdate
    from tests.factories import AccountFactory

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


async def test_get_account(db_pool: DBPool, account: Account):
    retrieved_account = await crud.account.get(db_pool, account.user.id)
    assert retrieved_account == account


async def test_get_account_but_user_not_found(db_pool: DBPool):
    user_id = uuid.uuid4()
    with pytest.raises(errors.UserNotFound) as excinfo:
        await crud.account.get(db_pool, user_id)

    assert str(excinfo.value) == f"No account for user with id: {user_id}"


async def test_list_all(db_pool: DBPool, account_factory: AccountFactory):
    await asyncio.gather(*(
        account_factory() for _ in range(2)
    ))
    accounts = await crud.account.list_all(db_pool, offset=0)
    assert len(accounts) == 2
    usernames = [account.user.username for account in accounts]
    assert usernames == sorted(usernames)


async def test_list_all_limit_offset(db_pool: DBPool, account_factory: AccountFactory):
    await asyncio.gather(*(
        account_factory() for _ in range(2)
    ))
    accounts = await crud.account.list_all(db_pool, offset=1, limit=1)
    assert len(accounts) == 1
    assert accounts[0].user.username


async def test_update_account(db_pool: DBPool, account_factory: AccountFactory):
    account = await account_factory("johnsmith@example.com")
    to_update: AccountUpdate = {"email": "johndoe@example.com"}
    updated_account = await crud.account.update(db_pool, account.user.id, to_update)
    assert updated_account.email == "johndoe@example.com"
    retrieved_account = await crud.account.get(db_pool, account.user.id)
    assert retrieved_account.email == "johndoe@example.com"
