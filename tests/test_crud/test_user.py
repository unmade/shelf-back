from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app import crud, errors

if TYPE_CHECKING:
    from app.typedefs import DBTransaction

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


async def test_create_user(tx: DBTransaction):
    await crud.user.create(tx, "user", "psswd")

    user = await tx.query_one("""
        SELECT User {
            username,
            password,
            namespace := (
                SELECT User.<owner[IS Namespace] {
                    path,
                    files := Namespace.<namespace[IS File] { name, path }
                }
                LIMIT 1
            )
        } FILTER .username = 'user'
        """)

    assert user.username == "user"
    assert user.password != "psswd"
    assert user.namespace.path == user.username
    assert len(user.namespace.files) == 1
    assert user.namespace.files[0].name == user.username
    assert user.namespace.files[0].path == "."


async def test_create_user_but_it_already_exists(tx: DBTransaction):
    await crud.user.create(tx, "user", "psswd")

    with pytest.raises(errors.UserAlreadyExists) as excinfo:
        await crud.user.create(tx, "user", "psswd")

    assert str(excinfo.value) == "Username 'user' is taken"


async def test_exists(tx: DBTransaction):
    await crud.user.create(tx, "user", "psswd")
    user = await tx.query_one("SELECT User FILTER .username = 'user'")
    assert await crud.user.exists(tx, user_id=user.id)


async def test_exists_but_it_is_not(tx: DBTransaction):
    assert not await crud.user.exists(tx, user_id=uuid.uuid4())


async def test_get_by_id(tx: DBTransaction):
    await crud.user.create(tx, "user", "psswd")
    user_id = (await tx.query_one("SELECT User FILTER .username = 'user'")).id
    user = await crud.user.get_by_id(tx, user_id=user_id)

    assert user.username == "user"
    assert user.superuser is False


async def test_get_by_id_but_it_not_found(tx: DBTransaction):
    user_id = uuid.uuid4()
    with pytest.raises(errors.UserNotFound) as excinfo:
        await crud.user.get_by_id(tx, user_id=user_id)

    assert str(excinfo.value) == f"No user with id: '{user_id}'"


async def test_get_password(tx: DBTransaction):
    await crud.user.create(tx, "user", "psswd")
    user_id, password = await crud.user.get_password(tx, username="user")

    assert user_id
    assert password


async def test_get_password_but_user_not_found(tx: DBTransaction):
    with pytest.raises(errors.UserNotFound) as excinfo:
        await crud.user.get_password(tx, username="user")

    assert str(excinfo.value) == "No user with username: 'user'"
