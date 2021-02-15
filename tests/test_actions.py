from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from app import actions, crud, errors
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
    await actions.create_folder(db_conn, user.namespace, path)

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
    await actions.create_folder(db_conn, user.namespace, path)

    with pytest.raises(errors.FileAlreadyExists):
        await actions.create_folder(db_conn, user.namespace, path.parent)

    assert storage.get(user.namespace.path / path.parent)


async def test_create_folder_but_parent_is_file(
    db_conn: Connection, user: User, file_factory
):
    await file_factory(user.id, path="file")

    with pytest.raises(errors.NotADirectory):
        await actions.create_folder(db_conn, user.namespace, "file/folder")


async def test_delete_immediately_file(db_conn: Connection, user: User, file_factory):
    file = await file_factory(user.id, path="file")
    path = Path(file.path)
    deleted_file = await actions.delete_immediately(db_conn, user.namespace, path)
    assert deleted_file.path == "file"

    with pytest.raises(errors.FileNotFound):
        storage.get(user.namespace.path / file.path)

    assert not await crud.file.exists(db_conn, user.namespace.path, path)


async def test_delete_immediately_but_file_not_exists(db_conn: Connection, user: User):
    with pytest.raises(errors.FileNotFound):
        await actions.delete_immediately(db_conn, user.namespace, "file")


async def test_empty_trash(db_conn: Connection, user: User, file_factory):
    await file_factory(user.id, path="Trash/a/b/c/d/file")
    await file_factory(user.id, path="file")

    await actions.empty_trash(db_conn, user.namespace)

    assert not list(storage.iterdir(user.namespace.path / "Trash"))
    trash = await db_conn.query_one("""
        SELECT File {
            size,
            file_count := (
                SELECT count((
                    SELECT File
                    FILTER .path LIKE 'Trash/%' AND .namespace.path = <str>$namespace
                ))
            ),
        }
        FILTER .path = 'Trash' AND .namespace.path = <str>$namespace
    """, namespace=str(user.namespace.path))

    assert trash.size == 0
    assert trash.file_count == 0
