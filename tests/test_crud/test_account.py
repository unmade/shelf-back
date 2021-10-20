from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app import crud, errors

if TYPE_CHECKING:
    from app.crud.account import AccountUpdate
    from app.entities import Account
    from app.typedefs import DBTransaction
    from tests.factories import AccountFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


async def test_create_account(tx: DBTransaction):
    await crud.user.create(tx, "johndoe", "psswd")
    await crud.account.create(tx, "johndoe", first_name="John")

    account = await tx.query_single("""
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


async def test_create_account_but_email_is_taken(tx: DBTransaction):
    await crud.user.create(tx, "user_a", "pssw")
    await crud.user.create(tx, "user_b", "pssw")
    await crud.account.create(tx, "user_a", email="user@example.com")

    with pytest.raises(errors.UserAlreadyExists) as excinfo:
        await crud.account.create(tx, "user_b", email="user@example.com")

    assert str(excinfo.value) == "Email 'user@example.com' is taken"


async def test_get_account(tx: DBTransaction, account: Account):
    retrieved_account = await crud.account.get(tx, account.user.id)
    assert retrieved_account == account


async def test_get_account_but_user_not_found(tx: DBTransaction):
    user_id = uuid.uuid4()
    with pytest.raises(errors.UserNotFound) as excinfo:
        await crud.account.get(tx, user_id)

    assert str(excinfo.value) == f"No account for user with id: {user_id}"


async def test_list_all(tx: DBTransaction, account_factory: AccountFactory):
    for _ in range(2):
        await account_factory()
    accounts = await crud.account.list_all(tx, offset=0)
    assert len(accounts) == 2
    usernames = [account.user.username for account in accounts]
    assert usernames == sorted(usernames)


async def test_list_all_limit_offset(
    tx: DBTransaction,
    account_factory: AccountFactory,
):
    for _ in range(2):
        await account_factory()
    accounts = await crud.account.list_all(tx, offset=1, limit=1)
    assert len(accounts) == 1
    assert accounts[0].user.username


async def test_update_account(tx: DBTransaction, account_factory: AccountFactory):
    account = await account_factory("johnsmith@example.com")
    to_update: AccountUpdate = {"email": "johndoe@example.com"}
    updated_account = await crud.account.update(tx, account.user.id, to_update)
    assert updated_account.email == "johndoe@example.com"
    retrieved_account = await crud.account.get(tx, account.user.id)
    assert retrieved_account.email == "johndoe@example.com"
