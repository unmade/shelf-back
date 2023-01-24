from __future__ import annotations

import uuid
from io import BytesIO
from typing import TYPE_CHECKING

import pytest

from app import actions, crud, errors
from app.entities import Exif
from app.storage import storage

if TYPE_CHECKING:
    from uuid import UUID

    from app.entities import Namespace
    from app.typedefs import DBAnyConn, DBClient, StrOrUUID
    from tests.factories import (
        BookmarkFactory,
        FileFactory,
        FileMetadataFactory,
        FingerprintFactory,
        FolderFactory,
        NamespaceFactory,
        SharedLinkFactory,
    )

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
            "last_name": "",
            "storage_quota": None,
        },
    ),
    (
        {
            "username": "johndoe",
            "password": "psswd",
            "email": "johndoe@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "storage_quota": 1024,
        },
        {
            "username": "johndoe",
            "password": "psswd",
            "email": "johndoe@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "storage_quota": 1024,
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
            storage_quota,
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


async def test_delete_immediately_file(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path, path="file")
    deleted_file = await actions.delete_immediately(db_client, namespace, file.path)
    assert deleted_file.path == "file"

    assert not await storage.exists(namespace.path, file.path)
    assert not await crud.file.exists(db_client, namespace.path, file.path)


async def test_delete_immediately_bookmarked_file(
    db_client: DBClient,
    namespace: Namespace,
    bookmark_factory: BookmarkFactory,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path, path="file")
    await bookmark_factory(namespace.owner.id, file.id)

    await actions.delete_immediately(db_client, namespace, file.path)

    assert not await storage.exists(namespace.path, file.path)
    assert not await crud.file.exists(db_client, namespace.path, file.path)


async def test_delete_immediately_folder(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, path="a/b/f.txt")
    await file_factory(namespace.path, path="a/b/f (1).txt")
    path = "a/b"
    deleted_folder = await actions.delete_immediately(db_client, namespace, path)
    assert deleted_folder.path == "a/b"

    assert await storage.exists(namespace.path, "a")
    assert await crud.file.exists(db_client, namespace.path, "a")
    assert not await storage.exists(namespace.path, "a/b")
    assert not await crud.file.exists(db_client, namespace.path, "a/b")
    assert not await storage.exists(namespace.path, "a/b/f.txt")
    assert not await crud.file.exists(db_client, namespace.path, "a/b/f (1).txt")


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
    await file_factory(namespace.path, path="Trash/f.txt")
    await file_factory(namespace.path, path="Trash/Documents/f.txt")
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


async def test_get_or_create_file_shared_link(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path)
    link = await actions.get_or_create_shared_link(db_client, namespace, file.path)
    assert len(link.token) > 16


async def test_get_or_create_folder_shared_link(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, "a/f.txt")
    link = await actions.get_or_create_shared_link(db_client, namespace, path="a")
    assert len(link.token) > 16


async def test_get_or_create_shared_link_is_idempotent(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path)
    link_a = await actions.get_or_create_shared_link(db_client, namespace, file.path)
    link_b = await actions.get_or_create_shared_link(db_client, namespace, file.path)
    assert link_a == link_b


async def test_get_thumbnail(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
    image_content: BytesIO,
):
    file = await file_factory(namespace.path, content=image_content)

    filecache, thumbnail = (
        await actions.get_thumbnail(db_client, namespace, file.id, size=64)
    )
    assert filecache == file
    assert len(thumbnail) < file.size
    assert isinstance(thumbnail, bytes)


async def test_get_thumbnail_but_file_not_found(
    db_client: DBClient,
    namespace: Namespace,
):
    file_id = uuid.uuid4()
    with pytest.raises(errors.FileNotFound):
        await actions.get_thumbnail(db_client, namespace, file_id, size=24)


async def test_get_thumbnail_but_file_in_other_namespace(
    db_client: DBClient,
    namespace_factory: NamespaceFactory,
    file_factory: FileFactory,
):
    namespace_a = await namespace_factory()
    namespace_b = await namespace_factory()
    file = await file_factory(namespace_b.path)
    with pytest.raises(errors.FileNotFound):
        await actions.get_thumbnail(db_client, namespace_a, file.id, size=24)


async def test_get_thumbnail_but_file_is_a_directory(
    db_client: DBClient,
    namespace: Namespace,
    folder_factory: FolderFactory,
):
    folder = await folder_factory(namespace.path)
    with pytest.raises(errors.IsADirectory):
        await actions.get_thumbnail(db_client, namespace, folder.id, size=64)


async def test_get_thumbnail_but_file_is_a_text_file(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path)
    with pytest.raises(errors.ThumbnailUnavailable):
        await actions.get_thumbnail(db_client, namespace, file.id, size=64)


async def test_get_thumbnail_but_file_is_not_thumbnailable(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path)
    with pytest.raises(errors.ThumbnailUnavailable):
        await actions.get_thumbnail(db_client, namespace, file.id, size=64)


async def test_move_file(
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


async def test_move_folder(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    await file_factory(namespace.path, path="a/b/f.txt")

    # rename folder 'b' to 'c'
    await actions.move(db_client, namespace, "a/b", "a/c")

    assert not await storage.exists(namespace.path, "a/b")
    assert not await crud.file.exists(db_client, namespace.path, "a/b")
    assert not await storage.exists(namespace.path, "a/b/f.txt")
    assert not await crud.file.exists(db_client, namespace.path, "a/b/f.txt")

    assert await storage.exists(namespace.path, "a/c")
    assert await crud.file.exists(db_client, namespace.path, "a/c")
    assert await storage.exists(namespace.path, "a/c/f.txt")
    assert await crud.file.exists(db_client, namespace.path, "a/c/f.txt")


async def test_move_with_case_sensitive_renaming(
    db_client: DBClient,
    namespace: Namespace,
    file_factory
):
    await file_factory(namespace.path, path="file.txt")

    # rename file 'file.txt' to 'File.txt'
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


async def test_reindex_creates_missing_files(
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

    await actions.reindex(db_client, namespace)

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


async def test_reindex_removes_dangling_files(
    db_client: DBClient,
    namespace: Namespace,
):
    # these files exist in the database, but not in the storage
    await crud.file.create_folder(db_client, namespace.path, "c/d")
    await crud.file.create(db_client, namespace.path, "c/d/f.txt", size=32)

    await actions.reindex(db_client, namespace)

    # ensure home size is updated
    home = await crud.file.get(db_client, namespace.path, ".")
    assert home.size == 0

    # ensure stale files has been deleted
    assert not await crud.file.exists(db_client, namespace.path, "c")
    assert not await crud.file.exists(db_client, namespace.path, "c/d")
    assert not await crud.file.exists(db_client, namespace.path, "c/d/f.txt")


async def test_reindex_do_nothing_when_files_consistent(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
):
    # these files exist both in the storage and in the database
    file = await file_factory(namespace.path, path="e/g/f.txt")

    await actions.reindex(db_client, namespace)

    # ensure home size is correct
    home = await crud.file.get(db_client, namespace.path, ".")
    assert home.size == file.size

    # ensure correct files remain the same
    assert await crud.file.exists(db_client, namespace.path, "e/g/f.txt")


async def test_reindex_files_content_restores_fingerprints(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
    image_content: BytesIO,
):
    await file_factory(namespace.path, "a/b/f.txt")
    img = await file_factory(namespace.path, "images/img.jpeg", content=image_content)
    await actions.reindex_files_content(db_client, namespace)
    assert await crud.fingerprint.get(db_client, file_id=img.id)


async def test_reindex_files_content_restores_file_metadata(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
    image_content_with_exif: BytesIO,
):
    await file_factory(namespace.path, "a/b/f.txt")
    content = image_content_with_exif
    img = await file_factory(namespace.path, "images/img.jpeg", content=content)
    await actions.reindex_files_content(db_client, namespace)
    meta = await crud.metadata.get(db_client, img.id)
    assert meta.data is not None


async def test_reindex_files_content_replaces_existing_fingerprint(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
    fingerprint_factory: FingerprintFactory,
    image_content: BytesIO,
):
    img = await file_factory(namespace.path, "images/img.jpeg", content=image_content)
    await fingerprint_factory(img.id, 1, 1, 1, 1)

    await actions.reindex_files_content(db_client, namespace)

    fingerprint = await crud.fingerprint.get(db_client, file_id=img.id)
    assert str(fingerprint.file_id) == img.id
    assert fingerprint.value == 0


async def test_reindex_files_content_replaces_existing_file_metadata(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
    file_metadata_factory: FileMetadataFactory,
    image_content_with_exif: BytesIO,
):
    content = image_content_with_exif
    exif = Exif(width=1280, height=800)
    img = await file_factory(namespace.path, "images/img.jpeg", content=content)
    await file_metadata_factory(img.id, data=exif)

    await actions.reindex_files_content(db_client, namespace)

    meta = await crud.metadata.get(db_client, file_id=img.id)
    assert meta.data is not None
    assert meta.data != exif


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


async def test_revoke_shared_link(
    db_client: DBClient,
    namespace: Namespace,
    file_factory: FileFactory,
    shared_link_factory: SharedLinkFactory,
):
    file = await file_factory(namespace.path)
    link = await shared_link_factory(file.id)
    await actions.revoke_shared_link(db_client, token=link.token)
    with pytest.raises(errors.SharedLinkNotFound):
        await crud.shared_link.get_by_token(db_client, link.token)


async def test_revoke_non_existing_shared_link(db_client: DBClient):
    await actions.revoke_shared_link(db_client, token="non-existing-token")
