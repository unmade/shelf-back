from __future__ import annotations

from io import BytesIO
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


async def test_move(db_conn: Connection, user: User, file_factory):
    await file_factory(user.id, path="a/b/f1")

    await actions.move(db_conn, user.namespace, "a/b", "a/c")

    assert not storage.is_exists(user.namespace.path / "a/b")
    assert not (await crud.file.exists(db_conn, user.namespace.path, "a/b"))

    assert storage.is_exists(user.namespace.path / "a/c")
    assert await crud.file.exists(db_conn, user.namespace.path, "a/c")


# todo: check that move is atomic - if something went
# wrong with storage, then database should rollback.


async def test_move_to_trash(db_conn: Connection, user: User, file_factory):
    await file_factory(user.id, path="a/b/f1")

    await actions.move_to_trash(db_conn, user.namespace, "a/b")

    assert not storage.is_exists(user.namespace.path / "a/b")
    assert not (await crud.file.exists(db_conn, user.namespace.path, "a/b"))

    assert storage.is_exists(user.namespace.path / "Trash/b")
    assert storage.is_exists(user.namespace.path / "Trash/b/f1")
    assert await crud.file.exists(db_conn, user.namespace.path, "Trash/b")
    assert await crud.file.exists(db_conn, user.namespace.path, "Trash/b/f1")


async def test_move_to_trash_autorename(db_conn: Connection, user: User, file_factory):
    namespace = user.namespace.path
    await file_factory(user.id, path="Trash/b")
    await file_factory(user.id, path="a/b/f1")

    file = await actions.move_to_trash(db_conn, user.namespace, "a/b")

    assert not storage.is_exists(namespace / "a/b")
    assert not (await crud.file.exists(db_conn, namespace, "a/b"))

    assert storage.is_exists(namespace / "Trash/b")
    assert not storage.is_exists(namespace / "Trash/b/f1")
    assert await crud.file.exists(db_conn, namespace, "Trash/b")
    assert not await crud.file.exists(db_conn, namespace, "Trash/b/f1")

    assert file.path.startswith("Trash")
    assert storage.is_exists(namespace / file.path)
    assert storage.is_exists(namespace / f"{file.path}/f1")
    assert await crud.file.exists(db_conn, namespace, file.path)
    assert await crud.file.exists(db_conn, namespace, f"{file.path}/f1")


@pytest.mark.parametrize("path", ["f.txt", "a/b/f.txt"])
async def test_save_file(db_conn: Connection, user: User, path):
    file = BytesIO(b"Dummy file")

    saved_file = await actions.save_file(db_conn, user.namespace, path, file)

    file_in_db = await crud.file.get(db_conn, user.namespace.path, path)
    file_in_storage = storage.get(user.namespace.path / path)

    assert saved_file == file_in_db

    assert file_in_db.name == Path(path).name
    assert file_in_db.path == str(path)
    assert file_in_db.size == 10

    assert file_in_db.size == file_in_storage.size
    # there can be slight gap between saving to the DB and the storage
    assert file_in_db.mtime == pytest.approx(file_in_storage.mtime)


async def test_save_file_but_name_already_taken(
    db_conn: Connection, user: User, file_factory,
):
    path = "a/b/f.txt"
    await file_factory(user.id, path=path)
    file = BytesIO(b"Dummy file")

    saved_file = await actions.save_file(db_conn, user.namespace, path, file)
    assert saved_file.name == "f (1).txt"


async def test_save_file_updates_parents_size(db_conn: Connection, user: User):
    path = Path("a/b/f.txt")
    file = BytesIO(b"Dummy file")

    await actions.save_file(db_conn, user.namespace, path, file)

    parents = await crud.file.get_many(db_conn, user.namespace.path, path.parents)
    for parent in parents:
        assert parent.size == 10
