from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.files.domain import File, Fingerprint
from app.infrastructure.database.edgedb.db import db_context
from app.infrastructure.database.edgedb.repositories.fingerprint import (
    _join_int2,
    _split_int8_by_int2,
)

if TYPE_CHECKING:
    from uuid import UUID

    from app.app.files.domain import Namespace
    from app.infrastructure.database.edgedb.repositories import FingerprintRepository

    from ..conftest import FileFactory, FingerprintFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


async def _get_by_file_id(file_id: UUID):
    return await db_context.get().query_required_single("""
        SELECT Fingerprint { part1, part2, part3, part4 }
        FILTER .file.id = <uuid>$file_id
    """, file_id=file_id)


@pytest.mark.parametrize(["given", "expected"], [
    [0, (0, 0, 0, 0)],
    [9_223_372_036_854_775_807, (65_535, 65_535, 65_535, 32_767)]
])
async def test_split_int8_by_int2(given, expected):
    assert _split_int8_by_int2(given) == expected


@pytest.mark.parametrize(["given", "expected"], [
    [(36, 36096, 52428, 61423), 17289262673409605668],
    [(65_535, 65_535, 65_535, 32_767), 9_223_372_036_854_775_807],
])
async def test_join_int2(given, expected):
    assert _join_int2(*reversed(given)) == expected


class TestIntersectAllWithPrefix:
    async def test(
        self,
        fingerprint_repo: FingerprintRepository,
        namespace: Namespace,
        file_factory: FileFactory,
        fingerprint_factory: FingerprintFactory
    ):
        ns_path = str(namespace.path)

        # full match
        fp1_1 = await fingerprint_factory(
            file_id=(await file_factory(ns_path, "f1.txt")).id,
            value=_join_int2(57472, 4722, 63684, 52728),
        )
        fp1_2 = await fingerprint_factory(
            file_id=(await file_factory(ns_path, "a/b/f1 (copy).txt")).id,
            value=_join_int2(57472, 4722, 63684, 52728),
        )

        # false positive match to 'fp1' and 'fp1_copy'
        fp1_3 = await fingerprint_factory(
            file_id=(await file_factory(ns_path, "a/f2 (false positive to f1).txt")).id,
            value=_join_int2(12914, 44137, 63684, 63929),
        )

        # these fingerprints has distance of 1
        fp2_1 = await fingerprint_factory(
            file_id=(await file_factory(ns_path, "f3.txt")).id,
            value=_join_int2(56797, 56781, 18381, 58597),
        )
        fp2_2 = await fingerprint_factory(
            file_id=(await file_factory(ns_path, "f3 (match).txt")).id,
            value=_join_int2(56797, 56797, 18381, 58597),
        )

        # this fingerprint has no match
        await fingerprint_factory(
            file_id=(await file_factory(ns_path, "a/f4.txt")).id,
            value=_join_int2(40, 36096, 36040, 65516),
        )

        # intersect in the home folder
        intersection = await fingerprint_repo.intersect_all_with_prefix(ns_path, "")
        assert len(intersection.keys()) == 5
        assert set(intersection[fp1_1]) == {fp1_2, fp1_3}
        assert set(intersection[fp1_2]) == {fp1_1, fp1_3}
        assert set(intersection[fp1_3]) == {fp1_1, fp1_2}
        assert set(intersection[fp2_1]) == {fp2_2}
        assert set(intersection[fp2_2]) == {fp2_1}

        # intersect in the folder 'a'
        intersection = await fingerprint_repo.intersect_all_with_prefix(ns_path, "a")
        assert len(intersection.keys()) == 2
        assert intersection[fp1_2] == [fp1_3]
        assert intersection[fp1_3] == [fp1_2]

        # intersect in the folder 'b'
        intersection = await fingerprint_repo.intersect_all_with_prefix(ns_path, "b")
        assert intersection == {}


class TestSave:
    async def test(
        self,
        fingerprint_repo: FingerprintRepository,
        file: File,
    ):
        fp = Fingerprint(file.id, value=17289262673409605668)
        await fingerprint_repo.save(fp)

        fingerprint = await _get_by_file_id(file.id)

        assert fingerprint.part1 == 36
        assert fingerprint.part2 == 36096
        assert fingerprint.part3 == 52428
        assert fingerprint.part4 == 61423

    async def test_when_fingerprint_already_exists(
        self,
        fingerprint_repo: FingerprintRepository,
        file: File,
    ):
        fp = Fingerprint(file.id, value=17289262673409605668)
        await fingerprint_repo.save(fp)
        with pytest.raises(Fingerprint.AlreadyExists):
            await fingerprint_repo.save(fp)

    async def test_when_file_does_not_exist(
        self, fingerprint_repo: FingerprintRepository
    ):
        fp = Fingerprint(file_id=uuid.uuid4(), value=24283937994761367101)
        with pytest.raises(File.NotFound):
            await fingerprint_repo.save(fp)


class TestSaveBatch:
    async def test(
        self,
        fingerprint_repo: FingerprintRepository,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        ns_path = str(namespace.path)
        files = [await file_factory(ns_path), await file_factory(ns_path)]
        fingerprints = [
            Fingerprint(files[0].id, value=17289262673409605668),
            Fingerprint(files[1].id, value=24283937994761367101),
        ]
        await fingerprint_repo.save_batch(fingerprints)

        fp_1 = await _get_by_file_id(fingerprints[0].file_id)
        assert fp_1.part1 == 36
        assert fp_1.part2 == 36096
        assert fp_1.part3 == 52428
        assert fp_1.part4 == 61423

        fp_2 = await _get_by_file_id(fingerprints[1].file_id)
        assert fp_2.part1 == 60989
        assert fp_2.part2 == 50524
        assert fp_2.part3 == 57585
        assert fp_2.part4 == 20737

    async def test_when_file_does_not_exist(
        self, fingerprint_repo: FingerprintRepository
    ):
        fp = Fingerprint(file_id=uuid.uuid4(), value=24283937994761367101)
        with pytest.raises(File.NotFound):
            await fingerprint_repo.save_batch([fp])
