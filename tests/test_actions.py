from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from app import actions, crud, errors
from app.storage import storage

if TYPE_CHECKING:
    from app.entities import Namespace
    from app.typedefs import DBPool
    from tests.factories import FileFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database(transaction=True)]


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

    account = await db_pool.query_single("""
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
    assert await db_pool.query_single("""
        SELECT NOT EXISTS (
            SELECT
                User
            FILTER
                .username = <str>$username
        )
    """, username="user_b")


async def test_create_folder(db_pool: DBPool, namespace: Namespace):
    path = Path("a/b/c")
    await actions.create_folder(db_pool, namespace, path)

    assert await storage.exists(namespace.path / path)

    query = """
        SELECT File { id }
        FILTER
            .path IN array_unpack(<array<str>>$paths)
            AND
            .namespace.path = <str>$namespace
    """

    folders = await db_pool.query(
        query,
        namespace=str(namespace.path),
        paths=[str(path)] + [str(p) for p in Path(path).parents]
    )

    assert len(folders) == 4


async def test_create_folder_but_folder_exists(db_pool: DBPool, namespace: Namespace):
    path = Path("a/b/c")
    await actions.create_folder(db_pool, namespace, path)

    with pytest.raises(errors.FileAlreadyExists):
        await actions.create_folder(db_pool, namespace, path.parent)

    assert await storage.exists(namespace.path / path.parent)


async def test_create_folder_but_parent_is_file(
    db_pool: DBPool,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, path="file")

    with pytest.raises(errors.NotADirectory):
        await actions.create_folder(db_pool, namespace, "file/folder")


async def test_delete_immediately_file(
    db_pool: DBPool,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path, path="file")
    path = Path(file.path)
    deleted_file = await actions.delete_immediately(db_pool, namespace, path)
    assert deleted_file.path == "file"

    assert not await storage.exists(namespace.path / file.path)
    assert not await crud.file.exists(db_pool, namespace.path, path)


async def test_delete_immediately_but_file_not_exists(
    db_pool: DBPool,
    namespace: Namespace,
):
    with pytest.raises(errors.FileNotFound):
        await actions.delete_immediately(db_pool, namespace, "file")


async def test_empty_trash(
    db_pool: DBPool,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, path="Trash/a/b/c/d/file")
    await file_factory(namespace.path, path="file")

    await actions.empty_trash(db_pool, namespace)

    assert not list(await storage.iterdir(namespace.path / "Trash"))

    trash = await crud.file.get(db_pool, namespace.path, "Trash")
    files = await crud.file.list_folder(db_pool, namespace.path, "Trash")
    assert trash.size == 0
    assert files == []


async def test_empty_trash_but_its_already_empty(
    db_pool: DBPool,
    namespace: Namespace,
):
    await actions.empty_trash(db_pool, namespace)

    trash = await crud.file.get(db_pool, namespace.path, "Trash")
    assert trash.size == 0


async def test_get_thumbnail(
    db_pool: DBPool,
    namespace: Namespace,
    file_factory: FileFactory,
    image_content: BytesIO,
):
    file = await file_factory(namespace.path, content=image_content)

    filecache, disksize, thumbnail = (
        await actions.get_thumbnail(db_pool, namespace, file.path, size=64)
    )
    assert filecache == file
    assert disksize < file.size
    assert isinstance(thumbnail, BytesIO)


async def test_get_thumbnail_but_file_not_found(
    db_pool: DBPool,
    namespace: Namespace,
):
    with pytest.raises(errors.FileNotFound):
        await actions.get_thumbnail(db_pool, namespace, "im.jpg", size=24)


async def test_get_thumbnail_but_file_is_a_directory(
    db_pool: DBPool,
    namespace: Namespace,
):
    with pytest.raises(errors.IsADirectory):
        await actions.get_thumbnail(db_pool, namespace, ".", size=64)


async def test_get_thumbnail_but_file_is_a_text_file(
    db_pool: DBPool,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path)
    with pytest.raises(errors.ThumbnailUnavailable):
        await actions.get_thumbnail(db_pool, namespace, file.path, size=64)


async def test_move(
    db_pool: DBPool,
    namespace: Namespace,
    file_factory
):
    await file_factory(namespace.path, path="a/b/f.txt")

    # rename folder 'b' to 'c'
    await actions.move(db_pool, namespace, "a/b", "a/c")

    assert not await storage.exists(namespace.path / "a/b")
    assert not await crud.file.exists(db_pool, namespace.path, "a/b")

    assert await storage.exists(namespace.path / "a/c")
    assert await crud.file.exists(db_pool, namespace.path, "a/c")


async def test_move_with_renaming(
    db_pool: DBPool,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, path="file.txt")

    # rename file 'file.txt' to '.file.txt'
    await actions.move(db_pool, namespace, "file.txt", ".file.txt")

    assert not await storage.exists(namespace.path / "file.txt")
    assert not await crud.file.exists(db_pool, namespace.path, "file.txt")

    assert await storage.exists(namespace.path / ".file.txt")
    assert await crud.file.exists(db_pool, namespace.path, ".file.txt")


async def test_move_but_next_path_is_already_taken(
    db_pool: DBPool,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, "a/b/x.txt")
    await file_factory(namespace.path, "a/c/y.txt")

    with pytest.raises(errors.FileAlreadyExists):
        await actions.move(db_pool, namespace, "a/b", "a/c")

    assert await storage.exists(namespace.path / "a/b")
    assert await crud.file.exists(db_pool, namespace.path, "a/b")


async def test_move_but_from_path_that_does_not_exists(
    db_pool: DBPool,
    namespace: Namespace,
):
    with pytest.raises(errors.FileNotFound):
        await actions.move(db_pool, namespace, "f", "a")


async def test_move_but_next_path_has_a_missing_parent(
    db_pool: DBPool,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, "f.txt")

    with pytest.raises(errors.MissingParent):
        await actions.move(db_pool, namespace, "f.txt", "a/f.txt")


async def test_move_but_next_path_is_not_a_folder(
    db_pool: DBPool,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, "x.txt")
    await file_factory(namespace.path, "y")

    with pytest.raises(errors.NotADirectory):
        await actions.move(db_pool, namespace, "x.txt", "y/x.txt")


@pytest.mark.parametrize("path", [".", "Trash", "trash"])
async def test_move_but_it_is_a_special_folder(
    db_pool: DBPool,
    namespace: Namespace,
    path: str,
):
    with pytest.raises(AssertionError) as excinfo:
        await actions.move(db_pool, namespace, path, "a/b")

    assert str(excinfo.value) == "Can't move Home or Trash folder."


@pytest.mark.parametrize(["a", "b"], [
    ("a/b", "a/b/b"),
    ("a/B", "A/b/B"),
])
async def test_move_but_paths_are_recursive(
    db_pool: DBPool,
    namespace: Namespace,
    a: str,
    b: str,
):
    with pytest.raises(AssertionError) as excinfo:
        await actions.move(db_pool, namespace, a, b)

    assert str(excinfo.value) == "Can't move to itself."


async def test_move_to_trash(
    db_pool: DBPool,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, path="a/b/f1")

    await actions.move_to_trash(db_pool, namespace, "a/b")

    assert not await storage.exists(namespace.path / "a/b")
    assert not await crud.file.exists(db_pool, namespace.path, "a/b")

    assert await storage.exists(namespace.path / "Trash/b")
    assert await storage.exists(namespace.path / "Trash/b/f1")
    assert await crud.file.exists(db_pool, namespace.path, "Trash/b")
    assert await crud.file.exists(db_pool, namespace.path, "Trash/b/f1")


async def test_move_to_trash_autorename(
    db_pool: DBPool,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, path="Trash/b")
    await file_factory(namespace.path, path="a/b/f1")

    file = await actions.move_to_trash(db_pool, namespace, "a/b")

    assert not await storage.exists(namespace.path / "a/b")
    assert not await crud.file.exists(db_pool, namespace.path, "a/b")

    assert await storage.exists(namespace.path / "Trash/b")
    assert await crud.file.exists(db_pool, namespace.path, "Trash/b")
    assert not await storage.exists(namespace.path / "Trash/b/f1")
    assert not await crud.file.exists(db_pool, namespace.path, "Trash/b/f1")

    assert file.path.startswith("Trash")
    assert await storage.exists(namespace.path / file.path)
    assert await storage.exists(namespace.path / f"{file.path}/f1")
    assert await crud.file.exists(db_pool, namespace.path, file.path)
    assert await crud.file.exists(db_pool, namespace.path, f"{file.path}/f1")


async def test_reconcile_creates_missing_files(db_pool: DBPool, namespace: Namespace):
    dummy_text = b"Dummy file"

    # these files exist in the storage, but not in the database
    await storage.makedirs(namespace.path / "a")
    await storage.makedirs(namespace.path / "b")
    await storage.save(namespace.path / "b/f.txt", content=BytesIO(dummy_text))

    await actions.reconcile(db_pool, namespace, ".")

    # ensure home size is correct
    home = await crud.file.get(db_pool, namespace.path, ".")
    assert home.size == 0

    # ensure missing files in the database has been created
    paths = ["a", "b", "b/f.txt"]
    a, b, f = await crud.file.get_many(db_pool, namespace.path, paths=paths)
    assert a.is_folder()
    assert a.size == 0
    assert b.is_folder()
    assert b.size == 0
    assert f.size == len(dummy_text)
    assert f.mediatype == 'text/plain'


@pytest.mark.xfail(
    reason="does not clean up folder content from db",
    strict=True,
)
async def test_reconcile_removes_stale_files(
    db_pool: DBPool,
    namespace: Namespace,
):
    # these files exist in the database, but not in the storage
    await crud.file.create_folder(db_pool, namespace.path, "c/d")
    await crud.file.create(db_pool, namespace.path, "c/d/f.txt", size=32)

    await actions.reconcile(db_pool, namespace, ".")

    # ensure home size is correct
    home = await crud.file.get(db_pool, namespace.path, ".")
    assert home.size == 0

    # ensure stale files has been deleted
    assert not await crud.file.exists(db_pool, namespace.path, "c")
    assert not await crud.file.exists(db_pool, namespace.path, "c/d")
    assert not await crud.file.exists(db_pool, namespace.path, "c/d/f.txt")


async def test_reconcile_do_nothing_when_files_consistent(
    db_pool: DBPool,
    namespace: Namespace,
    file_factory: FileFactory,
):
    # these files exist both in the storage and in the database
    file = await file_factory(namespace.path, path="e/g/f.txt")

    await actions.reconcile(db_pool, namespace, ".")

    # ensure home size is correct
    home = await crud.file.get(db_pool, namespace.path, ".")
    assert home.size == file.size

    # ensure correct files remain the same
    assert await crud.file.exists(db_pool, namespace.path, "e/g/f.txt")


@pytest.mark.parametrize("path", ["f.txt", "a/b/f.txt"])
async def test_save_file(db_pool: DBPool, namespace: Namespace, path: str):
    file = BytesIO(b"Dummy file")

    saved_file = await actions.save_file(db_pool, namespace, path, file)

    file_in_db = await crud.file.get(db_pool, namespace.path, path)

    assert saved_file == file_in_db

    assert file_in_db.name == Path(path).name
    assert file_in_db.path == str(path)
    assert file_in_db.size == 10
    assert file_in_db.mediatype == 'text/plain'

    size = await storage.size(namespace.path / path)
    assert file_in_db.size == size

    # there can be slight gap between saving to the DB and the storage
    mtime = await storage.get_modified_time(namespace.path / path)
    assert file_in_db.mtime == pytest.approx(mtime)


async def test_save_file_updates_parents_size(db_pool: DBPool, namespace: Namespace):
    path = Path("a/b/f.txt")
    file = BytesIO(b"Dummy file")

    await actions.save_file(db_pool, namespace, path, file)

    parents = await crud.file.get_many(db_pool, namespace.path, path.parents)
    for parent in parents:
        assert parent.size == 10


async def test_save_files_concurrently(db_pool: DBPool, namespace: Namespace):
    CONCURRENCY = 5
    parent = Path("a/b/c")
    paths = [parent / str(name) for name in range(CONCURRENCY)]
    files = [BytesIO(b"1") for _ in range(CONCURRENCY)]

    await actions.create_folder(db_pool, namespace, parent)

    await asyncio.gather(*(
        actions.save_file(db_pool, namespace, path, file)
        for path, file in zip(paths, files)
    ))

    count = len(await crud.file.get_many(db_pool, namespace.path, paths))
    assert count == CONCURRENCY

    home = await crud.file.get(db_pool, namespace.path, ".")
    assert home.size == CONCURRENCY


async def test_save_file_but_name_already_taken(
    db_pool: DBPool,
    namespace: Namespace,
    file_factory: FileFactory,
):
    path = "a/b/f.txt"
    await file_factory(namespace.path, path=path)
    file = BytesIO(b"Dummy file")

    saved_file = await actions.save_file(db_pool, namespace, path, file)
    assert saved_file.name == "f (1).txt"


async def test_save_file_but_path_is_a_file(
    db_pool: DBPool,
    namespace: Namespace,
    file_factory: FileFactory,
):
    path = "f.txt"
    await file_factory(namespace.path, path=path)
    file = BytesIO(b"Dummy file")

    with pytest.raises(errors.NotADirectory):
        await actions.save_file(db_pool, namespace, f"{path}/dummy", file)
