from __future__ import annotations

import os.path
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import PurePath
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app import errors
from app.app.files.domain import File, Fingerprint
from app.app.users.domain import Account

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.files.usecases import NamespaceUseCase

pytestmark = [pytest.mark.asyncio]


def _make_file(ns_path: str, path: str, size: int = 10) -> File:
    return File(
        id=uuid.uuid4(),
        ns_path=ns_path,
        name=os.path.basename(path),
        path=path,
        size=size,
        mediatype="image/jpeg",
    )


class TestAddFile:
    async def test_unlimited_storage_quota(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        dupefinder = cast(mock.MagicMock, ns_use_case.dupefinder)
        metadata = cast(mock.MagicMock, ns_use_case.metadata)
        ns_service = cast(mock.MagicMock, ns_use_case.namespace)
        user_service = cast(mock.MagicMock, ns_use_case.user)
        user_service.get_account = mock.AsyncMock(
            return_value=mock.MagicMock(Account, storage_quota=None)
        )

        ns_path, path, content = "admin", "f.txt", BytesIO(b"Dummy Content!")

        # WHEN
        result = await ns_use_case.add_file(ns_path, path, content)

        # THEN
        assert result == filecore.create_file.return_value
        filecore.create_file.assert_awaited_once_with(ns_path, path, content)
        dupefinder.track.assert_awaited_once_with(result.id, content)
        metadata.track.assert_awaited_once_with(result.id, content)

        owner_id = ns_service.get_by_path.return_value.owner_id
        user_service.get_account.assert_awaited_once_with(owner_id)
        ns_service.get_space_used_by_owner_id.assert_not_awaited()

    async def test_limited_storage_quota(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        dupefinder = cast(mock.MagicMock, ns_use_case.dupefinder)
        metadata = cast(mock.MagicMock, ns_use_case.metadata)
        ns_service = cast(mock.MagicMock, ns_use_case.namespace)
        ns_service.get_space_used_by_owner_id = mock.AsyncMock(return_value=512)
        user_service = cast(mock.MagicMock, ns_use_case.user)
        user_service.get_account = mock.AsyncMock(
            return_value=mock.MagicMock(Account, storage_quota=1024)
        )

        ns_path, path, content = "admin", "f.txt", BytesIO(b"Dummy Content!")

        # WHEN
        result = await ns_use_case.add_file(ns_path, path, content)

        # THEN
        assert result == filecore.create_file.return_value
        filecore.create_file.assert_awaited_once_with(ns_path, path, content)
        dupefinder.track.assert_awaited_once_with(result.id, content)
        metadata.track.assert_awaited_once_with(result.id, content)

        owner_id = ns_service.get_by_path.return_value.owner_id
        user_service.get_account.assert_awaited_once_with(owner_id)
        ns_service.get_space_used_by_owner_id.assert_awaited_once_with(owner_id)

    async def test_when_adding_to_trash_folder(self, ns_use_case: NamespaceUseCase):
        ns_path, path, content = "admin", "Trash/f.txt", BytesIO(b"Dummy Content!")
        with pytest.raises(File.MalformedPath):
            await ns_use_case.add_file(ns_path, path, content)

    async def test_when_max_upload_size_limit_is_exceeded(
        self, ns_use_case: NamespaceUseCase
    ):
        ns_path, path, content = "admin", "f.txt", BytesIO(b"Dummy Content!")
        with (
            mock.patch("app.config.FEATURES_UPLOAD_FILE_MAX_SIZE", 5),
            pytest.raises(File.TooLarge),
        ):
            await ns_use_case.add_file(ns_path, path, content)

    async def test_when_exceeding_storage_quota_limit(
        self, ns_use_case: NamespaceUseCase
    ):
        # GIVEN
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        dupefinder = cast(mock.MagicMock, ns_use_case.dupefinder)
        metadata = cast(mock.MagicMock, ns_use_case.metadata)
        ns_service = cast(mock.MagicMock, ns_use_case.namespace)
        ns_service.get_space_used_by_owner_id = mock.AsyncMock(return_value=1024)
        user_service = cast(mock.MagicMock, ns_use_case.user)
        user_service.get_account = mock.AsyncMock(
            return_value=mock.MagicMock(Account, storage_quota=1024)
        )

        ns_path, path, content = "admin", "f.txt", BytesIO(b"Dummy Content!")
        # WHEN
        with pytest.raises(errors.StorageQuotaExceeded):
            await ns_use_case.add_file(ns_path, path, content)

        # THEN
        filecore.create_file.assert_not_awaited()
        dupefinder.track.assert_not_awaited()
        metadata.track.assert_not_awaited()

        owner_id = ns_service.get_by_path.return_value.owner_id
        user_service.get_account.assert_awaited_once_with(owner_id)
        ns_service.get_space_used_by_owner_id.assert_awaited_once_with(owner_id)


class TestCreateFolder:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        # WHEN
        await ns_use_case.create_folder(ns_path, path)
        # THEN
        filecore.create_folder.assert_awaited_once_with(ns_path, path)


class TestDeleteItem:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        # WHEN
        await ns_use_case.delete_item(ns_path, path)
        # THEN
        filecore.delete.assert_awaited_once_with(ns_path, path)

    @pytest.mark.parametrize("path", [".", "Trash"])
    async def test_when_deleting_a_special_path(
        self, ns_use_case: NamespaceUseCase, path: str
    ):
        ns_path = "admin"
        with pytest.raises(AssertionError) as excinfo:
            await ns_use_case.delete_item(ns_path, path)
        assert str(excinfo.value) == "Can't delete Home or Trash folder."


class TestDownload:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        # WHEN
        result = await ns_use_case.download(ns_path, path)
        # THEN
        expected = (filecore.get_by_path.return_value, filecore.download.return_value)
        assert result == expected
        filecore.get_by_path.assert_called_once_with(ns_path, path)
        filecore.download.assert_called_once_with(filecore.get_by_path.return_value.id)


class TestEmptyTrash:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path = "admin"
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        # WHEN
        await ns_use_case.empty_trash(ns_path)
        # THEN
        filecore.empty_folder.assert_awaited_once_with(ns_path, "trash")


class TestFindDuplicates:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path = "admin"
        files = [_make_file(ns_path, f"{idx}.txt") for idx in range(4)]
        intersection = [
            [
                Fingerprint(file_id=files[0].id, value=14841886093006266496),
                Fingerprint(file_id=files[2].id, value=14841886093006266496),
            ],
            [
                Fingerprint(file_id=files[1].id, value=16493668159829433821),
                Fingerprint(file_id=files[3].id, value=16493668159830482397),
            ]
        ]
        dupefinder = cast(mock.MagicMock, ns_use_case.dupefinder)
        dupefinder.find_in_folder.return_value = intersection
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        filecore.get_by_id_batch.return_value = files
        # WHEN
        duplicates = await ns_use_case.find_duplicates(ns_path, ".")
        # THEN
        assert duplicates == [[files[0], files[2]], [files[1], files[3]]]
        dupefinder.find_in_folder.assert_awaited_once_with(ns_path, ".", 5)
        filecore.get_by_id_batch.assert_awaited_once()

    async def test_when_no_duplicates(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path = "admin"
        dupefinder = cast(mock.MagicMock, ns_use_case.dupefinder)
        dupefinder.find_in_folder.return_value = []
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        filecore.get_by_id_batch.return_value = []
        # WHEN
        duplicates = await ns_use_case.find_duplicates(ns_path, ".")
        # THEN
        assert duplicates == []
        dupefinder.find_in_folder.assert_awaited_once_with(ns_path, ".", 5)
        filecore.get_by_id_batch.assert_awaited_once()


class TestGetFileMetadata:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path, path = "admin", "home"
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        metadata = cast(mock.MagicMock, ns_use_case.metadata)
        # WHEN
        result = await ns_use_case.get_file_metadata(ns_path, path)
        # THEN
        assert result == metadata.get_by_file_id.return_value
        filecore.get_by_path.assert_awaited_once_with(ns_path, path)
        file = filecore.get_by_path.return_value
        metadata.get_by_file_id.assert_awaited_once_with(file.id)


class TestGetFileThumbnail:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path, path = "admin", "img.jpeg"
        file, thumbnail = _make_file(ns_path, path), mock.ANY
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        filecore.thumbnail.return_value = file, thumbnail
        # WHEN
        result = await ns_use_case.get_file_thumbnail(ns_path, file.id, size=32)
        # THEN
        assert result == filecore.thumbnail.return_value
        filecore.thumbnail.assert_awaited_once_with(file.id, size=32)

    async def test_when_file_does_not_exist(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path = "admin"
        file_id = str(uuid.uuid4())
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        filecore.thumbnail.side_effect = File.NotFound
        # WHEN/THEN
        with pytest.raises(File.NotFound):
            await ns_use_case.get_file_thumbnail(ns_path, file_id, size=32)
        filecore.thumbnail.assert_awaited_once_with(file_id, size=32)

    async def test_when_file_in_the_other_namespace(
        self, ns_use_case: NamespaceUseCase
    ):
        # GIVEN
        ns_path, path = "admin", "img.jpeg"
        file, thumbnail = _make_file(ns_path, path), mock.ANY
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        filecore.thumbnail.return_value = file, thumbnail
        # WHEN/THEN
        with pytest.raises(File.NotFound):
            await ns_use_case.get_file_thumbnail("user", file.id, size=32)
        filecore.thumbnail.assert_awaited_once_with(file.id, size=32)


class TestGetItemAtPath:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        # WHEN
        result = await ns_use_case.get_item_at_path(ns_path, path)
        # THEN
        assert result == filecore.get_by_path.return_value
        filecore.get_by_path.assert_awaited_once_with(ns_path, path)


class TestListFolder:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path, path = "admin", "home"
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        # WHEN
        result = await ns_use_case.list_folder(ns_path, path)
        # THEN
        assert result == filecore.list_folder.return_value
        filecore.list_folder.assert_awaited_once_with(ns_path, path)

    async def test_list_root_folder(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path, path = "admin", "."
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        filecore.list_folder.return_value = [
            _make_file(ns_path, "."),
            _make_file(ns_path, "trash"),
            _make_file(ns_path, "home"),
        ]
        # WHEN
        result = await ns_use_case.list_folder(ns_path, path)
        # THEN
        assert result == [filecore.list_folder.return_value[-1]]
        filecore.list_folder.assert_awaited_once_with(ns_path, path)


class TestMoveItem:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path, at_path, to_path = "admin", "a/b", "a/c"
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        # WHEN
        await ns_use_case.move_item(ns_path, at_path, to_path)
        # THEN
        filecore.move.assert_awaited_once_with(ns_path, at_path, to_path)

    @pytest.mark.parametrize("path", [".", "Trash", "trash"])
    async def test_when_moving_to_a_special_folder(
        self, ns_use_case: NamespaceUseCase, path
    ):
        ns_path = "admin"
        with pytest.raises(AssertionError) as excinfo:
            await ns_use_case.move_item(ns_path, path, "a/b")
        assert str(excinfo.value) == "Can't move Home or Trash folder."


class TestMoveItemToTrash:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path, path, next_path = "admin", "f.txt", PurePath("Trash/f.txt")
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        filecore.exists_at_path.return_value = False
        # WHEN
        await ns_use_case.move_item_to_trash(ns_path, path)
        # THEN
        filecore.exists_at_path.assert_awaited_once_with(ns_path, next_path)
        filecore.move.assert_awaited_once_with(ns_path, path, next_path)

    @mock.patch("app.timezone.now", return_value=datetime(2000, 1, 1, 19, 37))
    async def test_when_path_at_trash_exists(
        self, tz_now: MagicMock, ns_use_case: NamespaceUseCase
    ):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        next_path = PurePath("Trash/f 193700000000.txt")
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        filecore.exists_at_path.return_value = True
        # WHEN
        await ns_use_case.move_item_to_trash(ns_path, path)
        # THEN
        tz_now.assert_called_once_with()
        filecore.exists_at_path.assert_awaited_once_with(
            ns_path, PurePath("Trash/f.txt")
        )
        filecore.move.assert_awaited_once_with(ns_path, path, next_path)


class TestReindex:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_service = cast(mock.MagicMock, ns_use_case.namespace)
        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        # WHEN
        await ns_use_case.reindex("admin")
        # THEN
        ns_service.get_by_path.assert_awaited_once_with("admin")
        filecore.reindex.assert_awaited_once_with("admin", ".")


class TestReindexContents:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path = "admin"
        jpg_1 = _make_file(ns_path, "a/b/img (1).jpeg")
        jpg_2 = _make_file(ns_path, "a/b/img (2).jpeg")

        async def iter_by_mediatypes_result():
            yield [jpg_1]
            yield [jpg_2]

        filecore = cast(mock.MagicMock, ns_use_case.filecore)
        filecore.iter_by_mediatypes.return_value = iter_by_mediatypes_result()
        dupefinder = cast(mock.MagicMock, ns_use_case.dupefinder)
        meta_service = cast(mock.MagicMock, ns_use_case.metadata)

        # WHEN
        await ns_use_case.reindex_contents(ns_path)

        # THEN
        filecore.iter_by_mediatypes.assert_called_once()
        dupefinder_tracker = dupefinder.track_batch.return_value.__aenter__.return_value
        assert len(dupefinder_tracker.mock_calls) == 2
        metadata_tracker = meta_service.track_batch.return_value.__aenter__.return_value
        assert len(metadata_tracker.mock_calls) == 2
