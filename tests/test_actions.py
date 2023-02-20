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
