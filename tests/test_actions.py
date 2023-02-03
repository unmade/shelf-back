from __future__ import annotations

import uuid
from io import BytesIO
from typing import TYPE_CHECKING

import pytest

from app import actions, crud, errors
from app.entities import Exif
from app.infrastructure.storage import storage

if TYPE_CHECKING:

    from app.entities import Namespace
    from app.typedefs import DBClient
    from tests.factories import (
        FileFactory,
        FileMetadataFactory,
        FingerprintFactory,
        FolderFactory,
        NamespaceFactory,
        SharedLinkFactory,
    )

pytestmark = [pytest.mark.asyncio, pytest.mark.database(transaction=True)]


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


@pytest.mark.skip("waiting for refactoring to service method")
async def test_delete_immediately_bookmarked_file(
    db_client: DBClient,
    namespace: Namespace,
    bookmark_factory,
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
