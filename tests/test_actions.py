from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from app import actions, crud, errors
from app.entities import RelocationPath
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

    assert await storage.exists(expected["username"])
    assert await storage.exists(f"{expected['username']}/Trash")

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

    assert await storage.exists(user.namespace.path / path)

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

    assert await storage.exists(user.namespace.path / path.parent)


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

    assert not await storage.exists(user.namespace.path / file.path)
    assert not await crud.file.exists(db_pool, user.namespace.path, path)


async def test_delete_immediately_but_file_not_exists(db_pool: DBPool, user: User):
    with pytest.raises(errors.FileNotFound):
        await actions.delete_immediately(db_pool, user.namespace, "file")


async def test_empty_trash(db_pool: DBPool, user: User, file_factory):
    await file_factory(user.id, path="Trash/a/b/c/d/file")
    await file_factory(user.id, path="file")

    await actions.empty_trash(db_pool, user.namespace)

    assert not list(await storage.iterdir(user.namespace.path / "Trash"))

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
    await file_factory(user.id, path="a/b/f.txt")

    # rename folder 'b' to 'c'
    await actions.move(db_pool, user.namespace, "a/b", "a/c")

    assert not await storage.exists(user.namespace.path / "a/b")
    assert not await crud.file.exists(db_pool, user.namespace.path, "a/b")

    assert await storage.exists(user.namespace.path / "a/c")
    assert await crud.file.exists(db_pool, user.namespace.path, "a/c")


async def test_move_with_renaming(db_pool: DBPool, user: User, file_factory):
    namespace = user.namespace
    await file_factory(user.id, path="file.txt")

    # rename file 'file.txt' to '.file.txt'
    await actions.move(db_pool, namespace, "file.txt", ".file.txt")

    assert not await storage.exists(namespace.path / "file.txt")
    assert not await crud.file.exists(db_pool, namespace.path, "file.txt")

    assert await storage.exists(namespace.path / ".file.txt")
    assert await crud.file.exists(db_pool, namespace.path, ".file.txt")


async def test_move_but_next_path_is_already_taken(
    db_pool: DBPool, user: User, file_factory
):
    namespace = user.namespace
    await file_factory(user.id, "a/b/x.txt")
    await file_factory(user.id, "a/c/y.txt")

    with pytest.raises(errors.FileAlreadyExists):
        await actions.move(db_pool, namespace, "a/b", "a/c")

    assert await storage.exists(namespace.path / "a/b")
    assert await crud.file.exists(db_pool, namespace.path, "a/b")


async def test_move_but_from_path_that_not_exists(db_pool: DBPool, user: User):
    namespace = user.namespace

    with pytest.raises(errors.FileNotFound):
        await actions.move(db_pool, namespace, "f", "a")


async def test_move_but_to_path_with_a_missing_parent(
    db_pool: DBPool, user: User, file_factory,
):
    namespace = user.namespace
    await file_factory(user.id, "f.txt")

    with pytest.raises(errors.MissingParent):
        await actions.move(db_pool, namespace, "f.txt", "a/f.txt")


async def test_move_but_to_path_that_is_not_a_folder(
    db_pool: DBPool, user: User, file_factory
):
    namespace = user.namespace
    await file_factory(user.id, "x.txt")
    await file_factory(user.id, "y")

    with pytest.raises(errors.NotADirectory):
        await actions.move(db_pool, namespace, "x.txt", "y/x.txt")


@pytest.mark.parametrize("path", [".", "Trash", "trash"])
async def test_move_but_it_is_a_special_folder(db_pool: DBPool, user: User, path):
    namespace = user.namespace
    with pytest.raises(AssertionError) as excinfo:
        await actions.move(db_pool, namespace, path, "a/b")

    assert str(excinfo.value) == "Can't move Home or Trash folder."


@pytest.mark.parametrize(["a", "b"], [
    ("a/b", "a/b/b"),
    ("a/B", "A/b/B"),
])
async def test_move_but_paths_are_recursive(db_pool: DBPool, user: User, a, b):
    namespace = user.namespace
    with pytest.raises(AssertionError) as excinfo:
        await actions.move(db_pool, namespace, a, b)

    assert str(excinfo.value) == "Can't move to itself."


async def test_move_batch(db_pool: DBPool, user: User, file_factory):
    namespace = user.namespace
    paths = ["a.txt", "b.txt", "folder/a.txt", "folder/b.txt", "folder (1)/c.txt"]
    coros = (file_factory(user.id, path=path) for path in paths)
    await asyncio.gather(*coros)
    items = [
        RelocationPath(
            from_path="a.txt",
            to_path="folder (1)/a.txt",
        ),
        RelocationPath(
            from_path="folder",
            to_path="folder (1)/folder",
        ),
        RelocationPath(
            from_path="does not exists",
            to_path="folder (1)/does not exists",
        )
    ]

    result = await actions.move_batch(db_pool, namespace, items)
    assert len(result) == 3
    assert result[0].file is not None
    assert result[0].file.path == items[0].to_path
    assert result[0].err_code is None
    assert result[1].file is not None
    assert result[1].file.path == items[1].to_path
    assert result[1].err_code is None
    assert result[2].file is None
    assert result[2].err_code == errors.ErrorCode.file_not_found

    assert await crud.file.exists(db_pool, namespace.path, "b.txt")
    assert not await crud.file.exists(db_pool, namespace.path, "a.txt")
    assert not await crud.file.exists(db_pool, namespace.path, "folder")

    assert await crud.file.exists(db_pool, namespace.path, "folder (1)/a.txt")
    assert await crud.file.exists(db_pool, namespace.path, "folder (1)/c.txt")
    assert await crud.file.exists(db_pool, namespace.path, "folder (1)/folder/a.txt")
    assert await crud.file.exists(db_pool, namespace.path, "folder (1)/folder/b.txt")

    assert await storage.exists(namespace.path / "b.txt")
    assert await storage.exists(namespace.path / "folder (1)/a.txt")
    assert await storage.exists(namespace.path / "folder (1)/c.txt")
    assert await storage.exists(namespace.path / "folder (1)/folder/a.txt")
    assert await storage.exists(namespace.path / "folder (1)/folder/b.txt")


async def test_move_to_trash(db_pool: DBPool, user: User, file_factory):
    await file_factory(user.id, path="a/b/f1")

    await actions.move_to_trash(db_pool, user.namespace, "a/b")

    assert not await storage.exists(user.namespace.path / "a/b")
    assert not await crud.file.exists(db_pool, user.namespace.path, "a/b")

    assert await storage.exists(user.namespace.path / "Trash/b")
    assert await storage.exists(user.namespace.path / "Trash/b/f1")
    assert await crud.file.exists(db_pool, user.namespace.path, "Trash/b")
    assert await crud.file.exists(db_pool, user.namespace.path, "Trash/b/f1")


async def test_move_to_trash_autorename(db_pool: DBPool, user: User, file_factory):
    namespace = user.namespace.path
    await file_factory(user.id, path="Trash/b")
    await file_factory(user.id, path="a/b/f1")

    file = await actions.move_to_trash(db_pool, user.namespace, "a/b")

    assert not await storage.exists(namespace / "a/b")
    assert not await crud.file.exists(db_pool, namespace, "a/b")

    assert await storage.exists(namespace / "Trash/b")
    assert await crud.file.exists(db_pool, namespace, "Trash/b")
    assert not await storage.exists(namespace / "Trash/b/f1")
    assert not await crud.file.exists(db_pool, namespace, "Trash/b/f1")

    assert file.path.startswith("Trash")
    assert await storage.exists(namespace / file.path)
    assert await storage.exists(namespace / f"{file.path}/f1")
    assert await crud.file.exists(db_pool, namespace, file.path)
    assert await crud.file.exists(db_pool, namespace, f"{file.path}/f1")


async def test_reconcile(db_pool: DBPool, user: User, file_factory):
    namespace = user.namespace.path
    dummy_text = b"Dummy file"

    # these files exist in the storage, but not in the database
    await storage.makedirs(namespace / "a")
    await storage.makedirs(namespace / "b")
    await storage.save(namespace / "b/f.txt", content=BytesIO(dummy_text))

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

    assert saved_file == file_in_db

    assert file_in_db.name == Path(path).name
    assert file_in_db.path == str(path)
    assert file_in_db.size == 10
    assert file_in_db.mediatype == 'text/plain'

    size = await storage.size(user.namespace.path / path)
    assert file_in_db.size == size

    # there can be slight gap between saving to the DB and the storage
    mtime = await storage.get_modified_time(user.namespace.path / path)
    assert file_in_db.mtime == pytest.approx(mtime)


async def test_save_file_updates_parents_size(db_pool: DBPool, user: User):
    path = Path("a/b/f.txt")
    file = BytesIO(b"Dummy file")

    await actions.save_file(db_pool, user.namespace, path, file)

    parents = await crud.file.get_many(db_pool, user.namespace.path, path.parents)
    for parent in parents:
        assert parent.size == 10


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


async def test_save_file_but_path_is_a_file(db_pool: DBPool, user: User, file_factory):
    path = "f.txt"
    await file_factory(user.id, path=path)
    file = BytesIO(b"Dummy file")

    with pytest.raises(errors.NotADirectory):
        await actions.save_file(db_pool, user.namespace, f"{path}/dummy", file)
