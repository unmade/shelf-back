from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app import crud

if TYPE_CHECKING:
    from edgedb import AsyncIOConnection

pytestmark = [pytest.mark.asyncio]


async def test_create_user(db_conn: AsyncIOConnection):
    await crud.user.create(db_conn, "user", "psswd")

    user = await db_conn.query_one("""
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


async def test_create_user_but_it_already_exists(db_conn: AsyncIOConnection):
    await crud.user.create(db_conn, "user", "psswd")

    with pytest.raises(crud.user.UserAlreadyExists):
        await crud.user.create(db_conn, "user", "psswd")


async def test_exists(db_conn: AsyncIOConnection):
    await crud.user.create(db_conn, "user", "psswd")
    user = await db_conn.query_one("SELECT User FILTER .username = 'user'")
    assert await crud.user.exists(db_conn, user_id=user.id)


async def test_exists_but_it_is_not(db_conn: AsyncIOConnection):
    assert not await crud.user.exists(db_conn, user_id=uuid.uuid4())


async def test_get_by_id(db_conn: AsyncIOConnection):
    await crud.user.create(db_conn, "user", "psswd")
    user_id = (await db_conn.query_one("SELECT User FILTER .username = 'user'")).id
    user = await crud.user.get_by_id(db_conn, user_id=user_id)

    assert user.username == "user"
    assert str(user.namespace.path) == "user"


async def test_get_by_id_but_it_not_found(db_conn: AsyncIOConnection):
    with pytest.raises(crud.user.UserNotFound):
        await crud.user.get_by_id(db_conn, user_id=uuid.uuid4())


async def test_get_user_by_username(db_conn: AsyncIOConnection):
    await crud.user.create(db_conn, "user", "psswd")
    user = await crud.user.get_by_username(db_conn, username="user")

    assert user.username == "user"
    assert user.password


async def test_get_user_by_username_but_it_not_found(db_conn: AsyncIOConnection):
    with pytest.raises(crud.user.UserNotFound):
        await crud.user.get_by_username(db_conn, username="user")
