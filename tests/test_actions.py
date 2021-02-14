from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from app import actions, errors
from app.storage import storage

if TYPE_CHECKING:
    from edgedb import AsyncIOConnection as Connection
    from app.entities import User

pytestmark = [pytest.mark.asyncio]


async def test_create_account(db_conn: Connection):
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


async def test_create_account_but_username_is_taken(db_conn: Connection):
    await actions.create_account(db_conn, "user", "psswd")

    with pytest.raises(errors.UserAlreadyExists):
        await actions.create_account(db_conn, "user", "psswd")


async def test_create_folder(db_conn: Connection, user: User):
    path = Path("a/b/c")
    await actions.create_folder(db_conn, user.namespace.path, path)

    assert storage.get(user.namespace.path / path)

    query = """
        SELECT File { id }
        FILTER
            .path IN array_unpack(<array<str>>$paths)
            AND
            .namespace.path = <str>$namespace
    """

    folders = await db_conn.query(
        query,
        namespace=str(user.namespace.path),
        paths=[str(path)] + [str(p) for p in Path(path).parents]
    )

    assert len(folders) == 4


async def test_create_folder_but_folder_exists(db_conn: Connection, user: User):
    path = Path("a/b/c")
    await actions.create_folder(db_conn, user.namespace.path, path)

    with pytest.raises(errors.FileAlreadyExists):
        await actions.create_folder(db_conn, user.namespace.path, path.parent)

    assert storage.get(user.namespace.path / path.parent)


async def test_create_folder_but_parent_is_file(
    db_conn: Connection, user: User, file_factory
):
    await file_factory(user.id, path="file")

    with pytest.raises(errors.NotADirectory):
        await actions.create_folder(db_conn, user.namespace.path, "file/folder")
