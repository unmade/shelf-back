from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import orjson
import pytest

from app import crud, errors
from app.entities import Exif, FileMetadata

if TYPE_CHECKING:
    from app.entities import Namespace
    from app.typedefs import DBTransaction
    from tests.factories import FileFactory, FileMetadataFactory


pytestmark = [pytest.mark.asyncio, pytest.mark.database]


async def test_create(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
):
    exif = Exif(width=1280, height=800)
    file = await file_factory(namespace.path)

    await crud.metadata.create(tx, file.id, data=exif)

    meta = await tx.query_required_single("""
        SELECT FileMetadata { data, file: { id }}
        FILTER .file.id = <uuid>$file_id
        LIMIT 1
    """, file_id=file.id)

    assert str(meta.file.id) == file.id
    assert orjson.loads(meta.data) == {"type": "exif", "width": 1280, "height": 800}


async def test_create_but_target_file_does_not_exist(tx: DBTransaction):
    file_id = uuid.uuid4()
    with pytest.raises(errors.FileNotFound):
        await crud.metadata.create(tx, file_id, data=Exif())


async def test_create_batch(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file_a = await file_factory(namespace.path, "im_a.jpeg")
    exif_a = Exif(width=1280, height=800)
    file_b = await file_factory(namespace.path, "im_b.jpeg")
    exif_b = Exif(width=1440, height=900)

    data = [(file_a.path, exif_a), (file_b.path, exif_b)]

    await crud.metadata.create_batch(tx, namespace.path, data=data)

    result = await tx.query("""
        SELECT FileMetadata { data, file: { id } }
        ORDER BY .file.path ASC
    """)

    assert len(result) == 2
    assert str(result[0].file.id) == file_a.id
    assert orjson.loads(result[0].data) == exif_a.dict(exclude_none=True)
    assert str(result[1].file.id) == file_b.id
    assert orjson.loads(result[1].data) == exif_b.dict(exclude_none=True)


async def test_create_batch_but_file_metadata_already_exists(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file_a = await file_factory(namespace.path, "im_a.jpeg")
    exif_a = Exif(width=1280, height=800)
    file_b = await file_factory(namespace.path, "im_b.jpeg")
    exif_b = Exif(width=1440, height=900)

    data = [(file_a.path, exif_a)]

    await crud.metadata.create_batch(tx, namespace.path, data=data)

    data = [(file_a.path, exif_a), (file_b.path, exif_b)]

    with pytest.raises(errors.FileMetadataAlreadyExists):
        await crud.metadata.create_batch(tx, namespace.path, data=data)


async def test_create_batch_but_file_does_not_exist(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file_a = await file_factory(namespace.path, "im_a.jpeg")
    exif_a = Exif(width=1280, height=800)
    exif_b = Exif(width=1440, height=900)

    data = [(file_a.path, exif_a), ("im_b.jpeg", exif_b)]

    with pytest.raises(errors.FileNotFound):
        await crud.metadata.create_batch(tx, namespace.path, data=data)


async def test_delete_batch(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
    file_metadata_factory: FileMetadataFactory,
):
    ns_path = namespace.path
    files = [await file_factory(ns_path) for _ in range(3)]
    for file in files:
        await file_metadata_factory(file.id, Exif())

    await crud.metadata.delete_batch(tx, file_ids=[f.id for f in files[1:]])

    query = "SELECT FileMetadata { file: {id} }"
    objs = await tx.query(query)
    assert len(objs) == 1
    assert str(objs[0].file.id) == files[0].id


async def test_exists(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
    file_metadata_factory: FileMetadataFactory,
):
    exif = Exif(width=1280, height=800)
    file = await file_factory(namespace.path)
    await file_metadata_factory(file.id, data=exif)
    assert await crud.metadata.exists(tx, file_id=file.id)


async def test_exists_but_it_is_not(tx: DBTransaction):
    assert not await crud.metadata.exists(tx, file_id=uuid.uuid4())


async def test_get(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
    file_metadata_factory: FileMetadataFactory,
):
    exif = Exif(width=1280, height=800)
    file = await file_factory(namespace.path)
    await file_metadata_factory(file.id, data=exif)
    meta = await crud.metadata.get(tx, file_id=file.id)
    assert meta == FileMetadata(file_id=file.id, data=exif)


async def test_get_but_file_does_not_exist(tx: DBTransaction):
    file_id = uuid.uuid4()
    with pytest.raises(errors.FileMetadataNotFound):
        await crud.metadata.get(tx, file_id=file_id)


async def test_get_but_file_metadata_does_not_exists(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path)
    with pytest.raises(errors.FileMetadataNotFound):
        await crud.metadata.get(tx, file_id=file.id)
