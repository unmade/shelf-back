from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app import crud, errors

if TYPE_CHECKING:
    from app.entities import Namespace
    from app.typedefs import DBTransaction
    from tests.factories import FileFactory, FingerprintFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


@pytest.mark.parametrize(["given", "expected"], [
    [0, (0, 0, 0, 0)],
    [9_223_372_036_854_775_807, (65_535, 65_535, 65_535, 32_767)]
])
def test_split_int8_by_int2(given, expected):
    assert crud.fingerprint._split_int8_by_int2(given) == expected


@pytest.mark.parametrize(["given", "expected"], [
    [(36, 36096, 52428, 61423), 17289262673409605668],
    [(65_535, 65_535, 65_535, 32_767), 9_223_372_036_854_775_807],
])
def test_join_int2(given, expected):
    assert crud.fingerprint._join_int2(*reversed(given)) == expected


async def test_create_batch(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file_a = await file_factory(namespace.path, "im_a.jpeg")
    hash_a = 17289262673409605668
    file_b = await file_factory(namespace.path, "im_b.jpeg")
    hash_b = 24283937994761367101

    fingerprints = [(file_a.path, hash_a), (file_b.path, hash_b), None]

    await crud.fingerprint.create_batch(tx, namespace.path, fingerprints=fingerprints)

    result = await tx.query("""
        SELECT Fingerprint { part1, part2, part3, part4, file: { id } }
        ORDER BY .file.path ASC
    """)

    assert str(result[0].file.id) == file_a.id
    assert result[0].part1 == 36
    assert result[0].part2 == 36096
    assert result[0].part3 == 52428
    assert result[0].part4 == 61423

    assert str(result[1].file.id) == file_b.id
    assert result[1].part1 == 60989
    assert result[1].part2 == 50524
    assert result[1].part3 == 57585
    assert result[1].part4 == 20737


async def test_create_batch_but_fingerprint_already_exists(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
):
    ns_path = namespace.path

    file_a = await file_factory(namespace.path, "im_a.jpeg")
    hash_a = 17289262673409605668
    file_b = await file_factory(namespace.path, "im_b.jpeg")
    hash_b = 24283937994761367101

    fingerprints = [(file_b.path, hash_b)]
    await crud.fingerprint.create_batch(tx, ns_path, fingerprints=fingerprints)

    fingerprints = [(file_a.path, hash_a), (file_b.path, hash_b)]

    with pytest.raises(errors.FingerprintAlreadyExists):
        await crud.fingerprint.create_batch(tx, ns_path, fingerprints=fingerprints)


async def test_create_batch_but_file_does_not_exist(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
):
    ns_path = namespace.path

    file_a = await file_factory(namespace.path, "im_a.jpeg")
    hash_a = 17289262673409605668
    file_b_path = "im_b.jpeg"
    hash_b = 24283937994761367101

    fingerprints = [(file_a.path, hash_a), (file_b_path, hash_b)]
    with pytest.raises(errors.FileNotFound):
        await crud.fingerprint.create_batch(tx, ns_path, fingerprints=fingerprints)


async def test_delete_batch(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
    fingerprint_factory: FingerprintFactory,
):
    ns_path = namespace.path
    files = [await file_factory(ns_path) for _ in range(3)]
    for file in files:
        await fingerprint_factory(file.id, 0, 0, 0, 0)

    await crud.fingerprint.delete_batch(tx, file_ids=[f.id for f in files[1:]])

    query = "SELECT Fingerprint { file: {id} }"
    objs = await tx.query(query)
    assert len(objs) == 1
    assert str(objs[0].file.id) == files[0].id


async def test_get(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
    fingerprint_factory: FingerprintFactory,
):
    ns_path = namespace.path
    file = await file_factory(ns_path)
    expected = await fingerprint_factory(file.id, 0, 0, 0, 0)
    actual = await crud.fingerprint.get(tx, file_id=file.id)
    assert actual == expected


async def test_get_but_fingerprint_does_not_exists(tx: DBTransaction):
    with pytest.raises(errors.FingerprintNotFound):
        await crud.fingerprint.get(tx, file_id=uuid.uuid4())
