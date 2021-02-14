from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app import actions
from app.storage import storage

if TYPE_CHECKING:
    from edgedb import AsyncIOConnection

pytestmark = [pytest.mark.asyncio]


async def test_create_account(db_conn: AsyncIOConnection):
    await actions.create_account(db_conn, "user", "psswd")

    assert storage.get("user")
    assert storage.get("user/Trash")

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
    assert len(user.namespace.files) == 2
    assert user.namespace.files[0].name == user.username
    assert user.namespace.files[0].path == "."
    assert user.namespace.files[1].name == "Trash"
    assert user.namespace.files[1].path == "Trash"


async def test_create_account_but_username_is_taken(db_conn: AsyncIOConnection):
    await actions.create_account(db_conn, "user", "psswd")

    with pytest.raises(actions.UserAlreadyExists):
        await actions.create_account(db_conn, "user", "psswd")
