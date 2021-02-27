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
                    files := (
                        SELECT Namespace.<namespace[IS File] { name, path }
                        ORDER BY .path ASC
                    )
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

    trash = await crud.file.get(db_conn, user.namespace.path, "Trash")
    files = await crud.file.list_folder(db_conn, user.namespace.path, "Trash")
    assert trash.size == 0
    assert files == []


async def test_empty_trash_but_its_already_empty(db_conn: Connection, user: User):
    await actions.empty_trash(db_conn, user.namespace)

    trash = await crud.file.get(db_conn, user.namespace.path, "Trash")
    assert trash.size == 0


async def test_get_thumbnail(db_conn: Connection, user: User, image_factory):
    file = await image_factory(user.id)

    filecache, disksize, thumbnail = (
        await actions.get_thumbnail(db_conn, user.namespace, file.path, size=64)
    )
    assert filecache == file
    assert disksize < file.size
    assert isinstance(thumbnail, BytesIO)


async def test_get_thumbnail_but_file_not_found(db_conn: Connection, user: User):
    with pytest.raises(errors.FileNotFound):
        await actions.get_thumbnail(db_conn, user.namespace, "im.jpg", size=24)


async def test_get_thumbnail_but_file_is_a_folder(db_conn: Connection, user: User):
    with pytest.raises(errors.IsADirectory):
        await actions.get_thumbnail(db_conn, user.namespace, ".", size=64)


async def test_get_thumbnail_but_file_is_a_text_file(
    db_conn: Connection, user: User, file_factory
):
    file = await file_factory(user.id)
    with pytest.raises(errors.ThumbnailUnavailable):
        await actions.get_thumbnail(db_conn, user.namespace, file.path, size=64)


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


async def test_reconcile(db_conn: Connection, user: User, file_factory):
    namespace = user.namespace.path
    dummy_text = b"Dummy file"

    # these files exist in the storage, but not in the database
    storage.mkdir(namespace / "a")
    storage.mkdir(namespace / "b")
    storage.save(namespace / "b/f.txt", file=BytesIO(dummy_text))

    # these files exist in the database, but not in the storage
    await crud.file.create_folder(db_conn, namespace, "c/d")
    await crud.file.create(db_conn, namespace, "c/d/f.txt", size=32)

    # these files exist both in the storage and in the database
    file = await file_factory(user.id, path="e/g/f.txt")

    await actions.reconcile(db_conn, user.namespace, ".")

    # ensure home size is correct
    home = await crud.file.get(db_conn, namespace, ".")
    assert home.size == file.size + len(dummy_text)

    # ensure missing files in the database has been created
    a, b, f = await crud.file.get_many(db_conn, namespace, paths=["a", "b", "b/f.txt"])
    assert a.is_folder()
    assert a.size == 0
    assert b.is_folder()
    assert b.size == len(dummy_text)
    assert f.size == len(dummy_text)
    assert f.mediatype == 'text/plain'

    # ensure stale files has been deleted
    assert not await crud.file.exists(db_conn, namespace, "c")
    assert not await crud.file.exists(db_conn, namespace, "c/d")
    assert not await crud.file.exists(db_conn, namespace, "c/d/f.txt")

    # ensure correct files remain the same
    assert await crud.file.exists(db_conn, namespace, "e/g/f.txt")


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
    assert file_in_db.mediatype == 'text/plain'

    assert file_in_db.size == file_in_storage.size
    # there can be slight gap between saving to the DB and the storage
    assert file_in_db.mtime == pytest.approx(file_in_storage.mtime)


async def test_save_file_updates_parents_size(db_conn: Connection, user: User):
    path = Path("a/b/f.txt")
    file = BytesIO(b"Dummy file")

    await actions.save_file(db_conn, user.namespace, path, file)

    parents = await crud.file.get_many(db_conn, user.namespace.path, path.parents)
    for parent in parents:
        assert parent.size == 10


async def test_save_file_but_name_already_taken(
    db_conn: Connection, user: User, file_factory,
):
    path = "a/b/f.txt"
    await file_factory(user.id, path=path)
    file = BytesIO(b"Dummy file")

    saved_file = await actions.save_file(db_conn, user.namespace, path, file)
    assert saved_file.name == "f (1).txt"
