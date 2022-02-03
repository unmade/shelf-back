from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app import crud, errors

if TYPE_CHECKING:
    from app.entities import Namespace
    from app.typedefs import DBTransaction
    from tests.factories import FileFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


@pytest.mark.parametrize(["given", "expected"], [
    [0, (0, 0, 0, 0)],
    [9_223_372_036_854_775_807, (65_535, 65_535, 65_535, 32_767)]
])
def test_split_int8_by_int2(given, expected):
    assert crud.fingerprint._split_int8_by_int2(given) == expected


async def test_create(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path, "im.jpeg")
    fp = 17289262673409605668

    await crud.fingerprint.create(tx, file.id, fp=fp)

    fingerprint = await tx.query_single("""
        SELECT Fingerprint { part1, part2, part3, part4 }
        FILTER .file.id = <uuid>$file_id
    """, file_id=file.id)

    assert fingerprint.part1 == 36
    assert fingerprint.part2 == 36096
    assert fingerprint.part3 == 52428
    assert fingerprint.part4 == 61423


async def test_create_but_fingerprint_already_exists(
    tx: DBTransaction,
    namespace: Namespace,
    file_factory: FileFactory,
):
    file = await file_factory(namespace.path, "im.jpeg")
    fp = 17289262673409605668

    await crud.fingerprint.create(tx, file.id, fp=fp)

    with pytest.raises(errors.FingerprintAlreadyExists):
        await crud.fingerprint.create(tx, file.id, fp=fp)


async def test_create_but_file_does_not_exist(tx: DBTransaction):
    file_id = uuid.uuid4()
    fp = 17289262673409605668

    with pytest.raises(errors.FileNotFound):
        await crud.fingerprint.create(tx, file_id, fp=fp)
