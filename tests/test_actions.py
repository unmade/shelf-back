from __future__ import annotations

import asyncio
import uuid
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from app import actions, crud, errors
from app.storage import storage

if TYPE_CHECKING:
    from uuid import UUID

    from app.entities import Namespace
    from app.typedefs import DBAnyConn, DBClient, StrOrUUID
    from tests.factories import BookmarkFactory, FileFactory, FingerprintFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database(transaction=True)]


async def _get_bookmarks_id(conn: DBAnyConn, user_id: StrOrUUID) -> list[UUID]:
    query = """
        SELECT User { bookmarks: { id } }
        FILTER .id = <uuid>$user_id
    """
    user = await conn.query_required_single(query, user_id=user_id)
    return [entry.id for entry in user.bookmarks]


async def test_add_bookmark(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path)
    await actions.add_bookmark(db_client, namespace.owner.id, file.id)
    bookmarks = await _get_bookmarks_id(db_client, user_id=namespace.owner.id)
    assert len(bookmarks) == 1
    assert str(bookmarks[0]) == file.id


async def test_add_bookmark_but_user_does_not_exists(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path)
    user_id = uuid.uuid4()
    with pytest.raises(errors.UserNotFound):
        await actions.add_bookmark(db_client, user_id, file.id)


@pytest.mark.parametrize(["given", "expected"], [
    (
        {
            "username": "JohnDoe",
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
async def test_create_account(db_client: DBClient, given, expected):
    await actions.create_account(db_client, **given)

    assert await storage.exists(expected["username"], ".")
    assert await storage.exists(f"{expected['username']}", "Trash")

    account = await db_client.query_required_single("""
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


async def test_create_account_but_username_is_taken(db_client: DBClient):
    await actions.create_account(db_client, "user", "psswd")

    with pytest.raises(errors.UserAlreadyExists):
        await actions.create_account(db_client, "user", "psswd")


async def test_create_account_but_email_is_taken(db_client: DBClient):
    email = "user@example.com"
    await actions.create_account(db_client, "user_a", "psswd", email=email)

    with pytest.raises(errors.UserAlreadyExists) as excinfo:
        await actions.create_account(db_client, "user_b", "psswd", email=email)

    assert str(excinfo.value) == "Email 'user@example.com' is taken"
    assert await db_client.query_required_single("""
        SELECT NOT EXISTS (
            SELECT
                User
            FILTER
                .username = <str>$username
        )
    """, username="user_b")


async def test_create_folder(db_client: DBClient, namespace: Namespace):
    path = Path("a/b/c")
    await actions.create_folder(db_client, namespace, path)

    assert await storage.exists(namespace.path, path)

    query = """
        SELECT File { id }
        FILTER
            .path IN array_unpack(<array<str>>$paths)
            AND
            .namespace.path = <str>$namespace
    """

    folders = await db_client.query(
        query,
        namespace=str(namespace.path),
        paths=[str(path)] + [str(p) for p in Path(path).parents]
    )

    assert len(folders) == 4


async def test_create_folder_but_folder_exists(
    db_client: DBClient,
    namespace: Namespace,
):
    path = Path("a/b/c")
    await actions.create_folder(db_client, namespace, path)

    with pytest.raises(errors.FileAlreadyExists):
        await actions.create_folder(db_client, namespace, path.parent)

    assert await storage.exists(namespace.path, path.parent)


async def test_create_folder_but_parent_is_file(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, path="file")

    with pytest.raises(errors.NotADirectory):
        await actions.create_folder(db_client, namespace, "file/folder")


async def test_delete_immediately_file(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path, path="file")
    path = Path(file.path)
    deleted_file = await actions.delete_immediately(db_client, namespace, path)
    assert deleted_file.path == "file"

    assert not await storage.exists(namespace.path, file.path)
    assert not await crud.file.exists(db_client, namespace.path, path)


async def test_delete_immediately_but_file_not_exists(
    db_client: DBClient,
    namespace: Namespace,
):
    with pytest.raises(errors.FileNotFound):
        await actions.delete_immediately(db_client, namespace, "file")


async def test_empty_trash(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, path="Trash/a/b/c/d/file")
    await file_factory(namespace.path, path="file")

    await actions.empty_trash(db_client, namespace)

    assert not list(await storage.iterdir(namespace.path, "Trash"))

    trash = await crud.file.get(db_client, namespace.path, "Trash")
    files = await crud.file.list_folder(db_client, namespace.path, "Trash")
    assert trash.size == 0
    assert files == []


async def test_empty_trash_but_its_already_empty(
    db_client: DBClient,
    namespace: Namespace,
):
    await actions.empty_trash(db_client, namespace)

    trash = await crud.file.get(db_client, namespace.path, "Trash")
    assert trash.size == 0


async def test_find_duplicates(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
    fingerprint_factory: FingerprintFactory,
):
    ns_path = str(namespace.path)

    file_1 = await file_factory(ns_path, "f1.txt")
    file_1_copy = await file_factory(ns_path, "a/b/f1 (copy).txt")

    file_2 = await file_factory(ns_path, "a/f2 (false positive to f1).txt")

    file_3 = await file_factory(ns_path, "f3.txt")
    file_3_match = await file_factory(ns_path, "f3 (match).txt")

    # full match
    fp1 = await fingerprint_factory(file_1.id, 57472, 4722, 63684, 52728)
    fp1_copy = await fingerprint_factory(file_1_copy.id, 57472, 4722, 63684, 52728)

    # false positive match to 'fp1' and 'fp1_copy'
    fp2 = await fingerprint_factory(file_2.id, 12914, 44137, 63684, 63929)

    # these fingerprints has distance of 1
    fp3 = await fingerprint_factory(file_3.id, 56797, 56781, 18381, 58597)
    fp3_match = await fingerprint_factory(file_3_match.id, 56797, 56797, 18381, 58597)

    # find duplicates in the home folder
    dupes = await actions.find_duplicates(db_client, namespace, ".")
    assert len(dupes) == 2
    assert set(dupes[0]) == {fp1, fp1_copy}
    assert set(dupes[1]) == {fp3, fp3_match}

    # find duplicates in the home folder with max distance
    dupes = await actions.find_duplicates(db_client, namespace, ".", max_distance=30)
    assert len(dupes) == 2
    assert set(dupes[0]) == {fp1, fp1_copy, fp2}
    assert set(dupes[1]) == {fp3, fp3_match}

    # find duplicates in the folder 'a'
    dupes = await actions.find_duplicates(db_client, namespace, "a")
    assert len(dupes) == 0


async def test_get_thumbnail(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
    image_content: BytesIO,
):
    file = await file_factory(namespace.path, content=image_content)

    filecache, disksize, thumbnail = (
        await actions.get_thumbnail(db_client, namespace, file.path, size=64)
    )
    assert filecache == file
    assert disksize < file.size
    assert isinstance(thumbnail, BytesIO)


async def test_get_thumbnail_but_file_not_found(
    db_client: DBClient,
    namespace: Namespace,
):
    with pytest.raises(errors.FileNotFound):
        await actions.get_thumbnail(db_client, namespace, "im.jpg", size=24)


async def test_get_thumbnail_but_file_is_a_directory(
    db_client: DBClient,
    namespace: Namespace,
):
    with pytest.raises(errors.IsADirectory):
        await actions.get_thumbnail(db_client, namespace, ".", size=64)


async def test_get_thumbnail_but_file_is_a_text_file(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path)
    with pytest.raises(errors.ThumbnailUnavailable):
        await actions.get_thumbnail(db_client, namespace, file.path, size=64)


async def test_move(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, path="a/b/f.txt")

    # rename folder 'b' to 'c'
    await actions.move(db_client, namespace, "a/b", "a/c")

    assert not await storage.exists(namespace.path, "a/b")
    assert not await crud.file.exists(db_client, namespace.path, "a/b")

    assert await storage.exists(namespace.path, "a/c")
    assert await crud.file.exists(db_client, namespace.path, "a/c")


async def test_move_with_renaming(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, path="file.txt")

    # rename file 'file.txt' to '.file.txt'
    await actions.move(db_client, namespace, "file.txt", ".file.txt")

    assert not await storage.exists(namespace.path, "file.txt")
    assert not await crud.file.exists(db_client, namespace.path, "file.txt")

    assert await storage.exists(namespace.path, ".file.txt")
    assert await crud.file.exists(db_client, namespace.path, ".file.txt")


async def test_move_with_case_sensitive_renaming(
    db_client: DBClient,
    namespace: Namespace,
    file_factory
):
    await file_factory(namespace.path, path="file.txt")

    # rename file 'file.txt' to '.file.txt'
    await actions.move(db_client, namespace, "file.txt", "File.txt")

    # assert not await storage.exists(namespace.path, "file.txt")
    # assert not await crud.file.exists(db_client, namespace.path, "file.txt")

    assert await storage.exists(namespace.path, "File.txt")
    assert await crud.file.exists(db_client, namespace.path, "File.txt")


async def test_move_but_next_path_is_already_taken(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, "a/b/x.txt")
    await file_factory(namespace.path, "a/c/y.txt")

    with pytest.raises(errors.FileAlreadyExists):
        await actions.move(db_client, namespace, "a/b", "a/c")

    assert await storage.exists(namespace.path, "a/b")
    assert await crud.file.exists(db_client, namespace.path, "a/b")


async def test_move_but_from_path_that_does_not_exists(
    db_client: DBClient,
    namespace: Namespace,
):
    with pytest.raises(errors.FileNotFound):
        await actions.move(db_client, namespace, "f", "a")


async def test_move_but_next_path_has_a_missing_parent(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, "f.txt")

    with pytest.raises(errors.MissingParent):
        await actions.move(db_client, namespace, "f.txt", "a/f.txt")


async def test_move_but_next_path_is_not_a_folder(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, "x.txt")
    await file_factory(namespace.path, "y")

    with pytest.raises(errors.NotADirectory):
        await actions.move(db_client, namespace, "x.txt", "y/x.txt")


@pytest.mark.parametrize("path", [".", "Trash", "trash"])
async def test_move_but_it_is_a_special_folder(
    db_client: DBClient,
    namespace: Namespace,
    path: str,
):
    with pytest.raises(AssertionError) as excinfo:
        await actions.move(db_client, namespace, path, "a/b")

    assert str(excinfo.value) == "Can't move Home or Trash folder."


@pytest.mark.parametrize(["a", "b"], [
    ("a/b", "a/b/b"),
    ("a/B", "A/b/B"),
])
async def test_move_but_paths_are_recursive(
    db_client: DBClient,
    namespace: Namespace,
    a: str,
    b: str,
):
    with pytest.raises(AssertionError) as excinfo:
        await actions.move(db_client, namespace, a, b)

    assert str(excinfo.value) == "Can't move to itself."


async def test_move_to_trash(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, path="a/b/f1")

    await actions.move_to_trash(db_client, namespace, "a/b")

    assert not await storage.exists(namespace.path, "a/b")
    assert not await crud.file.exists(db_client, namespace.path, "a/b")

    assert await storage.exists(namespace.path, "Trash/b")
    assert await storage.exists(namespace.path, "Trash/b/f1")
    assert await crud.file.exists(db_client, namespace.path, "Trash/b")
    assert await crud.file.exists(db_client, namespace.path, "Trash/b/f1")


async def test_move_to_trash_autorename(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, path="Trash/b")
    await file_factory(namespace.path, path="a/b/f1")

    file = await actions.move_to_trash(db_client, namespace, "a/b")

    assert not await storage.exists(namespace.path, "a/b")
    assert not await crud.file.exists(db_client, namespace.path, "a/b")

    assert await storage.exists(namespace.path, "Trash/b")
    assert await crud.file.exists(db_client, namespace.path, "Trash/b")
    assert not await storage.exists(namespace.path, "Trash/b/f1")
    assert not await crud.file.exists(db_client, namespace.path, "Trash/b/f1")

    assert file.path.startswith("Trash")
    assert await storage.exists(namespace.path, file.path)
    assert await storage.exists(namespace.path, f"{file.path}/f1")
    assert await crud.file.exists(db_client, namespace.path, file.path)
    assert await crud.file.exists(db_client, namespace.path, f"{file.path}/f1")


async def test_reconcile_creates_missing_files(
    db_client: DBClient,
    namespace: Namespace,
    image_content: BytesIO,
):
    dummy_text = b"Dummy file"

    # these files exist in the storage, but not in the database
    await storage.makedirs(namespace.path, "a")
    await storage.makedirs(namespace.path, "b")
    await storage.save(namespace.path, "b/f.txt", content=BytesIO(dummy_text))
    await storage.save(namespace.path, "im.jpeg", content=image_content)

    await actions.reconcile(db_client, namespace)

    # ensure home size is correct
    home = await crud.file.get(db_client, namespace.path, ".")
    assert home.size == 1661

    # ensure missing files in the database has been created
    paths = ["a", "b", "b/f.txt", "im.jpeg"]
    a, b, f, i = await crud.file.get_many(db_client, namespace.path, paths=paths)
    assert a.is_folder()
    assert a.size == 0
    assert b.is_folder()
    assert b.size == 10
    assert f.size == len(dummy_text)
    assert f.mediatype == "text/plain"
    assert i.mediatype == "image/jpeg"
    assert i.size == image_content.seek(0, 2)

    # ensure fingerprints were created
    query = """
        SELECT Fingerprint { file: { id }}
        FILTER .file.id IN {array_unpack(<array<uuid>>$file_ids)}
    """
    fingerprints = await db_client.query(query, file_ids=[a.id, b.id, f.id, i.id])
    assert len(fingerprints) == 1
    assert str(fingerprints[0].file.id) == i.id


async def test_reconcile_removes_dangling_files(
    db_client: DBClient,
    namespace: Namespace,
):
    # these files exist in the database, but not in the storage
    await crud.file.create_folder(db_client, namespace.path, "c/d")
    await crud.file.create(db_client, namespace.path, "c/d/f.txt", size=32)

    await actions.reconcile(db_client, namespace)

    # ensure home size is updated
    home = await crud.file.get(db_client, namespace.path, ".")
    assert home.size == 0

    # ensure stale files has been deleted
    assert not await crud.file.exists(db_client, namespace.path, "c")
    assert not await crud.file.exists(db_client, namespace.path, "c/d")
    assert not await crud.file.exists(db_client, namespace.path, "c/d/f.txt")


async def test_reconcile_do_nothing_when_files_consistent(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    # these files exist both in the storage and in the database
    file = await file_factory(namespace.path, path="e/g/f.txt")

    await actions.reconcile(db_client, namespace)

    # ensure home size is correct
    home = await crud.file.get(db_client, namespace.path, ".")
    assert home.size == file.size

    # ensure correct files remain the same
    assert await crud.file.exists(db_client, namespace.path, "e/g/f.txt")


async def test_remove_bookmark(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
    bookmark_factory: BookmarkFactory,
):
    file = await file_factory(namespace.path)
    await bookmark_factory(namespace.owner.id, file.id)
    bookmarks = await _get_bookmarks_id(db_client, user_id=namespace.owner.id)
    assert len(bookmarks) == 1
    await actions.remove_bookmark(db_client, namespace.owner.id, file.id)
    bookmarks = await _get_bookmarks_id(db_client, user_id=namespace.owner.id)
    assert len(bookmarks) == 0


async def test_remove_bookmark_but_user_does_not_exists(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path)
    user_id = uuid.uuid4()
    with pytest.raises(errors.UserNotFound):
        await actions.remove_bookmark(db_client, user_id, file.id)


@pytest.mark.parametrize("path", ["f.txt", "a/b/f.txt"])
async def test_save_file(db_client: DBClient, namespace: Namespace, path: str):
    file = BytesIO(b"Dummy file")

    saved_file = await actions.save_file(db_client, namespace, path, file)

    file_in_db = await crud.file.get(db_client, namespace.path, path)

    assert saved_file == file_in_db

    assert file_in_db.name == Path(path).name
    assert file_in_db.path == str(path)
    assert file_in_db.size == 10
    assert file_in_db.mediatype == 'text/plain'

    size = await storage.size(namespace.path, path)
    assert file_in_db.size == size

    # there can be slight gap between saving to the DB and the storage
    mtime = await storage.get_modified_time(namespace.path, path)
    assert file_in_db.mtime == pytest.approx(mtime)


async def test_save_file_updates_parents_size(
    db_client: DBClient,
    namespace: Namespace,
):
    path = Path("a/b/f.txt")
    file = BytesIO(b"Dummy file")

    await actions.save_file(db_client, namespace, path, file)

    parents = await crud.file.get_many(db_client, namespace.path, path.parents)
    assert len(parents) == 3
    for parent in parents:
        assert parent.size == 10


async def test_save_files_concurrently(db_client: DBClient, namespace: Namespace):
    CONCURRENCY = 5
    parent = Path("a/b/c")
    paths = [parent / str(name) for name in range(CONCURRENCY)]
    files = [BytesIO(b"1") for _ in range(CONCURRENCY)]

    await actions.create_folder(db_client, namespace, parent)

    await asyncio.gather(*(
        actions.save_file(db_client, namespace, path, file)
        for path, file in zip(paths, files)
    ))

    count = len(await crud.file.get_many(db_client, namespace.path, paths))
    assert count == CONCURRENCY

    home = await crud.file.get(db_client, namespace.path, ".")
    assert home.size == CONCURRENCY


async def test_save_files_creates_fingerprint(
    db_client: DBClient,
    namespace: Namespace,
    image_content: BytesIO,
):
    path = Path("im.jpeg")

    image_in_db = await actions.save_file(db_client, namespace, path, image_content)
    assert image_in_db.mediatype == "image/jpeg"

    query = """
        SELECT EXISTS (
            SELECT
                Fingerprint
            FILTER
                .file.id = <uuid>$file_id
        )
    """

    assert await db_client.query_required_single(query, file_id=image_in_db.id)


async def test_save_file_but_name_already_taken(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    path = "a/b/f.txt"
    await file_factory(namespace.path, path=path)
    file = BytesIO(b"Dummy file")

    saved_file = await actions.save_file(db_client, namespace, path, file)
    assert saved_file.name == "f (1).txt"


async def test_save_file_but_path_is_a_file(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    path = "f.txt"
    await file_factory(namespace.path, path=path)
    file = BytesIO(b"Dummy file")

    with pytest.raises(errors.NotADirectory):
        await actions.save_file(db_client, namespace, f"{path}/dummy", file)
