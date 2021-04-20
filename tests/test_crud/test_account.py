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
