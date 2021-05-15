from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from app import actions, crud, errors
from app.storage import storage

if TYPE_CHECKING:
    from app.entities import User
    from app.typedefs import DBPool

pytestmark = [pytest.mark.asyncio]


@pytest.mark.parametrize(["given", "expected"], [
    (
        {
            "username": "johndoe",
            "password": "psswd"
        },
        {
            "username": "johndoe",
            "password": "psswd",
            "email": None,
            "first_name": "",
            "last_name": ""
        },
    ),
    (
        {
            "username": "johndoe",
            "password": "psswd",
            "email": "johndoe@example.com",
            "first_name": "John",
            "last_name": "Doe"
        },
        {
            "username": "johndoe",
            "password": "psswd",
            "email": "johndoe@example.com",
            "first_name": "John",
            "last_name": "Doe"
        },
    ),
])
async def test_create_account(db_pool: DBPool, given, expected):
    await actions.create_account(db_pool, **given)

    assert storage.get(expected["username"])
    assert storage.get(f"{expected['username']}/Trash")

    account = await db_pool.query_one("""
        SELECT Account {
            email,
            first_name,
            last_name,
            user: {
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
                ),
            }
        }
        FILTER
            .user.username = <str>$username
        LIMIT 1
    """, username=expected["username"])

    assert account.email == expected["email"]
    assert account.first_name == expected["first_name"]
    assert account.last_name == expected["last_name"]

    user = account.user
    assert user.username == expected["username"]
    assert user.password != expected["password"]

    namespace = user.namespace
    assert namespace.path == user.username
    assert len(namespace.files) == 2
    assert namespace.files[0].name == user.username
    assert namespace.files[0].path == "."
    assert namespace.files[1].name == "Trash"
    assert namespace.files[1].path == "Trash"


async def test_create_account_but_username_is_taken(db_pool: DBPool):
    await actions.create_account(db_pool, "user", "psswd")

    with pytest.raises(errors.UserAlreadyExists):
        await actions.create_account(db_pool, "user", "psswd")


async def test_create_account_but_email_is_taken(db_pool: DBPool):
    email = "user@example.com"
    await actions.create_account(db_pool, "user_a", "psswd", email=email)

    with pytest.raises(errors.UserAlreadyExists) as excinfo:
        await actions.create_account(db_pool, "user_b", "psswd", email=email)

    assert str(excinfo.value) == "Email 'user@example.com' is taken"
    assert await db_pool.query_one("""
        SELECT NOT EXISTS (
            SELECT
                User
            FILTER
                .username = <str>$username
        )
    """, username="user_b")


async def test_create_folder(db_pool: DBPool, user: User):
    path = Path("a/b/c")
    await actions.create_folder(db_pool, user.namespace, path)

    assert storage.get(user.namespace.path / path)

    query = """
        SELECT File { id }
        FILTER
            .path IN array_unpack(<array<str>>$paths)
            AND
            .namespace.path = <str>$namespace
    """

    folders = await db_pool.query(
        query,
        namespace=str(user.namespace.path),
        paths=[str(path)] + [str(p) for p in Path(path).parents]
    )

    assert len(folders) == 4


async def test_create_folder_but_folder_exists(db_pool: DBPool, user: User):
    path = Path("a/b/c")
    await actions.create_folder(db_pool, user.namespace, path)

    with pytest.raises(errors.FileAlreadyExists):
        await actions.create_folder(db_pool, user.namespace, path.parent)

    assert storage.get(user.namespace.path / path.parent)


async def test_create_folder_but_parent_is_file(
    db_pool: DBPool, user: User, file_factory
):
    await file_factory(user.id, path="file")

    with pytest.raises(errors.NotADirectory):
        await actions.create_folder(db_pool, user.namespace, "file/folder")


async def test_delete_immediately_file(db_pool: DBPool, user: User, file_factory):
    file = await file_factory(user.id, path="file")
    path = Path(file.path)
    deleted_file = await actions.delete_immediately(db_pool, user.namespace, path)
    assert deleted_file.path == "file"

    with pytest.raises(errors.FileNotFound):
        storage.get(user.namespace.path / file.path)

    assert not await crud.file.exists(db_pool, user.namespace.path, path)


async def test_delete_immediately_but_file_not_exists(db_pool: DBPool, user: User):
    with pytest.raises(errors.FileNotFound):
        await actions.delete_immediately(db_pool, user.namespace, "file")


async def test_empty_trash(db_pool: DBPool, user: User, file_factory):
    await file_factory(user.id, path="Trash/a/b/c/d/file")
    await file_factory(user.id, path="file")

    await actions.empty_trash(db_pool, user.namespace)

    assert not list(storage.iterdir(user.namespace.path / "Trash"))

    trash = await crud.file.get(db_pool, user.namespace.path, "Trash")
    files = await crud.file.list_folder(db_pool, user.namespace.path, "Trash")
    assert trash.size == 0
    assert files == []


async def test_empty_trash_but_its_already_empty(db_pool: DBPool, user: User):
    await actions.empty_trash(db_pool, user.namespace)

    trash = await crud.file.get(db_pool, user.namespace.path, "Trash")
    assert trash.size == 0


async def test_get_thumbnail(db_pool: DBPool, user: User, image_factory):
    file = await image_factory(user.id)

    filecache, disksize, thumbnail = (
        await actions.get_thumbnail(db_pool, user.namespace, file.path, size=64)
    )
    assert filecache == file
    assert disksize < file.size
    assert isinstance(thumbnail, BytesIO)


async def test_get_thumbnail_but_file_not_found(db_pool: DBPool, user: User):
    with pytest.raises(errors.FileNotFound):
        await actions.get_thumbnail(db_pool, user.namespace, "im.jpg", size=24)


async def test_get_thumbnail_but_file_is_a_folder(db_pool: DBPool, user: User):
    with pytest.raises(errors.IsADirectory):
        await actions.get_thumbnail(db_pool, user.namespace, ".", size=64)


async def test_get_thumbnail_but_file_is_a_text_file(
    db_pool: DBPool, user: User, file_factory
):
    file = await file_factory(user.id)
    with pytest.raises(errors.ThumbnailUnavailable):
        await actions.get_thumbnail(db_pool, user.namespace, file.path, size=64)


async def test_move(db_pool: DBPool, user: User, file_factory):
    await file_factory(user.id, path="a/b/f1")

    await actions.move(db_pool, user.namespace, "a/b", "a/c")

    assert not storage.is_exists(user.namespace.path / "a/b")
    assert not (await crud.file.exists(db_pool, user.namespace.path, "a/b"))

    assert storage.is_exists(user.namespace.path / "a/c")
    assert await crud.file.exists(db_pool, user.namespace.path, "a/c")


# todo: check that move is atomic - if something went
# wrong with storage, then database should rollback.


async def test_move_to_trash(db_pool: DBPool, user: User, file_factory):
    await file_factory(user.id, path="a/b/f1")

    await actions.move_to_trash(db_pool, user.namespace, "a/b")

    assert not storage.is_exists(user.namespace.path / "a/b")
    assert not (await crud.file.exists(db_pool, user.namespace.path, "a/b"))

    assert storage.is_exists(user.namespace.path / "Trash/b")
    assert storage.is_exists(user.namespace.path / "Trash/b/f1")
    assert await crud.file.exists(db_pool, user.namespace.path, "Trash/b")
    assert await crud.file.exists(db_pool, user.namespace.path, "Trash/b/f1")


async def test_move_to_trash_autorename(db_pool: DBPool, user: User, file_factory):
    namespace = user.namespace.path
    await file_factory(user.id, path="Trash/b")
    await file_factory(user.id, path="a/b/f1")

    file = await actions.move_to_trash(db_pool, user.namespace, "a/b")

    assert not storage.is_exists(namespace / "a/b")
    assert not (await crud.file.exists(db_pool, namespace, "a/b"))

    assert storage.is_exists(namespace / "Trash/b")
    assert not storage.is_exists(namespace / "Trash/b/f1")
    assert await crud.file.exists(db_pool, namespace, "Trash/b")
    assert not await crud.file.exists(db_pool, namespace, "Trash/b/f1")

    assert file.path.startswith("Trash")
    assert storage.is_exists(namespace / file.path)
    assert storage.is_exists(namespace / f"{file.path}/f1")
    assert await crud.file.exists(db_pool, namespace, file.path)
    assert await crud.file.exists(db_pool, namespace, f"{file.path}/f1")


async def test_reconcile(db_pool: DBPool, user: User, file_factory):
    namespace = user.namespace.path
    dummy_text = b"Dummy file"

    # these files exist in the storage, but not in the database
    storage.mkdir(namespace / "a")
    storage.mkdir(namespace / "b")
    storage.save(namespace / "b/f.txt", file=BytesIO(dummy_text))

    # these files exist in the database, but not in the storage
    await crud.file.create_folder(db_pool, namespace, "c/d")
    await crud.file.create(db_pool, namespace, "c/d/f.txt", size=32)

    # these files exist both in the storage and in the database
    file = await file_factory(user.id, path="e/g/f.txt")

    await actions.reconcile(db_pool, user.namespace, ".")

    # ensure home size is correct
    home = await crud.file.get(db_pool, namespace, ".")
    assert home.size == file.size + len(dummy_text)

    # ensure missing files in the database has been created
    a, b, f = await crud.file.get_many(db_pool, namespace, paths=["a", "b", "b/f.txt"])
    assert a.is_folder()
    assert a.size == 0
    assert b.is_folder()
    assert b.size == len(dummy_text)
    assert f.size == len(dummy_text)
    assert f.mediatype == 'text/plain'

    # ensure stale files has been deleted
    assert not await crud.file.exists(db_pool, namespace, "c")
    assert not await crud.file.exists(db_pool, namespace, "c/d")
    assert not await crud.file.exists(db_pool, namespace, "c/d/f.txt")

    # ensure correct files remain the same
    assert await crud.file.exists(db_pool, namespace, "e/g/f.txt")


@pytest.mark.parametrize("path", ["f.txt", "a/b/f.txt"])
async def test_save_file(db_pool: DBPool, user: User, path):
    file = BytesIO(b"Dummy file")

    saved_file = await actions.save_file(db_pool, user.namespace, path, file)

    file_in_db = await crud.file.get(db_pool, user.namespace.path, path)
    file_in_storage = storage.get(user.namespace.path / path)

    assert saved_file == file_in_db

    assert file_in_db.name == Path(path).name
    assert file_in_db.path == str(path)
    assert file_in_db.size == 10
    assert file_in_db.mediatype == 'text/plain'

    assert file_in_db.size == file_in_storage.size
    # there can be slight gap between saving to the DB and the storage
    assert file_in_db.mtime == pytest.approx(file_in_storage.mtime)


async def test_save_file_updates_parents_size(db_pool: DBPool, user: User):
    path = Path("a/b/f.txt")
    file = BytesIO(b"Dummy file")

    await actions.save_file(db_pool, user.namespace, path, file)

    parents = await crud.file.get_many(db_pool, user.namespace.path, path.parents)
    for parent in parents:
        assert parent.size == 10


@pytest.mark.skip("see: https://github.com/edgedb/edgedb-python/issues/185")
async def test_save_files_concurrently(db_pool: DBPool, user: User):
    CONCURRENCY = 8
    parent = Path("a/b/c")
    paths = [parent / str(name) for name in range(CONCURRENCY)]
    files = [BytesIO(b"1") for _ in range(CONCURRENCY)]

    await actions.create_folder(db_pool, user.namespace, parent)

    await asyncio.gather(*(
        actions.save_file(db_pool, user.namespace, path, file)
        for path, file in zip(paths, files)
    ))

    count = len(await crud.file.get_many(db_pool, user.namespace.path, paths))
    assert count == CONCURRENCY

    home = await crud.file.get(db_pool, user.namespace.path, ".")
    assert home.size == CONCURRENCY


async def test_save_file_but_name_already_taken(
    db_pool: DBPool, user: User, file_factory,
):
    path = "a/b/f.txt"
    await file_factory(user.id, path=path)
    file = BytesIO(b"Dummy file")

    saved_file = await actions.save_file(db_pool, user.namespace, path, file)
    assert saved_file.name == "f (1).txt"
