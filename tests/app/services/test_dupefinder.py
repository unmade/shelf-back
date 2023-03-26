from __future__ import annotations

import uuid
from typing import IO, TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.files.domain import Fingerprint
from app.app.services.dupefinder import _Tracker

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.files.repositories.fingerprint import MatchResult
    from app.app.services import DuplicateFinderService

pytestmark = [pytest.mark.asyncio]


class TestFindInFolder:
    @mock.patch("app.app.services.DuplicateFinderService._group")
    async def test(self, _group, dupefinder: DuplicateFinderService):
        ns_path = "admin"
        groups = await dupefinder.find_in_folder(ns_path, "myfolder")
        assert groups == _group.return_value
        db = cast(mock.MagicMock, dupefinder.db)
        db.fingerprint.intersect_all_with_prefix.assert_awaited_once_with(
            ns_path, prefix="myfolder/"
        )
        _group.assert_called_once_with(
            db.fingerprint.intersect_all_with_prefix.return_value,
            max_distance=5,
        )


class TestGroup:
    @pytest.fixture
    def match_result(self):
        fp1_1 = Fingerprint(file_id=uuid.uuid4(), value=14841886093006266496)
        fp1_2 = Fingerprint(file_id=uuid.uuid4(), value=14841886093006266496)
        # match to 'fp1_1' and 'fp1_2' but distance is too big
        fp1_3 = Fingerprint(file_id=uuid.uuid4(), value=17994687309725381234)

        fp2_1 = Fingerprint(file_id=uuid.uuid4(), value=16493668159829433821)
        fp2_2 = Fingerprint(file_id=uuid.uuid4(), value=16493668159830482397)

        return {
            fp1_1: [fp1_2, fp1_3],
            fp1_2: [fp1_1, fp1_3],
            fp1_3: [fp1_1, fp1_2],
            fp2_1: [fp2_2],
            fp2_2: [fp2_1],
        }

    def test(self, dupefinder: DuplicateFinderService, match_result: MatchResult):
        groups = dupefinder._group(match_result, max_distance=5)
        fp1_1, fp1_2, _, fp2_1, fp2_2 = match_result.keys()
        assert groups == [
            [fp1_1, fp1_2],
            [fp2_1, fp2_2],
        ]

    def test_with_zero_distance(
        self, dupefinder: DuplicateFinderService, match_result: MatchResult
    ):
        groups = dupefinder._group(match_result, max_distance=0)
        fp1_1, fp1_2, *_ = match_result.keys()
        assert groups == [
            [fp1_1, fp1_2],
        ]

    def test_with_loose_distance(
        self, dupefinder: DuplicateFinderService, match_result: MatchResult
    ):
        groups = dupefinder._group(match_result, max_distance=30)
        fp1_1, fp1_2, fp1_3, fp2_1, fp2_2 = match_result.keys()
        assert groups == [
            [fp1_1, fp1_2, fp1_3],
            [fp2_1, fp2_2],
        ]


@mock.patch("app.hashes.dhash")
class TestTrack:
    async def test(
        self,
        dhash: MagicMock,
        dupefinder: DuplicateFinderService,
        image_content: IO[bytes],
    ):
        file_id = str(uuid.uuid4())
        dhash.return_value = 0
        await dupefinder.track(file_id, image_content)
        dhash.assert_called_once_with(image_content, mediatype="image/jpeg")
        db: MagicMock = cast(mock.MagicMock, dupefinder.db)
        db.fingerprint.save.assert_awaited_once_with(
            Fingerprint(file_id, value=0)
        )

    async def test_when_dhash_is_none(
        self,
        dhash: MagicMock,
        dupefinder: DuplicateFinderService,
        image_content: IO[bytes],
    ):
        file_id = str(uuid.uuid4())
        dhash.return_value = None
        await dupefinder.track(file_id, image_content)
        dhash.assert_called_once_with(image_content, mediatype="image/jpeg")
        db: MagicMock = cast(mock.MagicMock, dupefinder.db)
        db.fingerprint.save.assert_not_awaited()


@mock.patch("app.hashes.dhash")
class TestTrackBatch:
    async def test(
        self,
        dhash: MagicMock,
        dupefinder: DuplicateFinderService,
        image_content: IO[bytes],
    ):
        file_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        dhash.return_value = 0
        async with dupefinder.track_batch() as tracker:
            await tracker.add(file_ids[0], image_content)
            await tracker.add(file_ids[1], image_content)

        expected = _Tracker()
        expected._items = [
            Fingerprint(file_ids[0], value=0),
            Fingerprint(file_ids[1], value=0),
        ]
        db = cast(mock.MagicMock, dupefinder.db)
        db.fingerprint.save_batch.assert_awaited_once_with(expected)
