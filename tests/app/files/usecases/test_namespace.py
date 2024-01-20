from __future__ import annotations

import uuid
from datetime import datetime
from typing import IO, TYPE_CHECKING, AsyncIterator, cast
from unittest import mock

import pytest

from app.app.files.domain import File, Fingerprint, Path
from app.app.users.domain import Account
from app.config import config

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.files.domain import AnyPath, IFileContent
    from app.app.files.usecases import NamespaceUseCase

pytestmark = [pytest.mark.anyio]


async def _aiter(content: IO[bytes]) -> AsyncIterator[bytes]:
    for chunk in content:
        yield chunk


def _make_file(ns_path: str, path: AnyPath, size: int = 10) -> File:
    return File(
        id=uuid.uuid4(),
        ns_path=ns_path,
        name=Path(path).name,
        path=Path(path),
        chash=uuid.uuid4().hex,
        size=size,
        mediatype="image/jpeg",
    )


def _make_account(storage_quota: int | None = None) -> Account:
    return Account(
        id=uuid.uuid4(),
        username="admin",
        email=None,
        first_name="",
        last_name="",
        storage_quota=storage_quota or None,
    )


class TestAddFile:
    async def test_unlimited_storage_quota(
        self, ns_use_case: NamespaceUseCase, content: IFileContent
    ):
        # GIVEN
        audit_trail = cast(mock.MagicMock, ns_use_case.audit_trail)
        file_service = cast(mock.MagicMock, ns_use_case.file)
        dupefinder = cast(mock.MagicMock, ns_use_case.dupefinder)
        metadata = cast(mock.MagicMock, ns_use_case.metadata)
        ns_service = cast(mock.MagicMock, ns_use_case.namespace)
        thumbnailer = cast(mock.MagicMock, ns_use_case.thumbnailer)
        user_service = cast(mock.MagicMock, ns_use_case.user)
        user_service.get_account.return_value = _make_account(storage_quota=None)

        ns_path, path = "admin", "f.txt"

        # WHEN
        result = await ns_use_case.add_file(ns_path, path, content)

        # THEN
        assert result == file_service.create_file.return_value
        file_service.create_file.assert_awaited_once_with(ns_path, path, content)
        dupefinder.track.assert_awaited_once_with(result.id, content.file)
        metadata.track.assert_awaited_once_with(result.id, content.file)
        thumbnailer.generate_thumbnails_async.assert_awaited_once_with(
            result.id, sizes=[64, 512, 2304]
        )

        owner_id = ns_service.get_by_path.return_value.owner_id
        user_service.get_account.assert_awaited_once_with(owner_id)
        ns_service.get_space_used_by_owner_id.assert_not_awaited()
        audit_trail.file_added.assert_called_once_with(result)

    async def test_limited_storage_quota(
        self, ns_use_case: NamespaceUseCase, content: IFileContent
    ):
        # GIVEN
        audit_trail = cast(mock.MagicMock, ns_use_case.audit_trail)
        file_service = cast(mock.MagicMock, ns_use_case.file)
        dupefinder = cast(mock.MagicMock, ns_use_case.dupefinder)
        metadata = cast(mock.MagicMock, ns_use_case.metadata)
        ns_service = cast(mock.MagicMock, ns_use_case.namespace)
        ns_service.get_space_used_by_owner_id = mock.AsyncMock(return_value=512)
        thumbnailer = cast(mock.MagicMock, ns_use_case.thumbnailer)
        user_service = cast(mock.MagicMock, ns_use_case.user)
        user_service.get_account.return_value = _make_account(storage_quota=1024)

        ns_path, path = "admin", "f.txt"

        # WHEN
        result = await ns_use_case.add_file(ns_path, path, content)

        # THEN
        assert result == file_service.create_file.return_value
        file_service.create_file.assert_awaited_once_with(ns_path, path, content)
        dupefinder.track.assert_awaited_once_with(result.id, content.file)
        metadata.track.assert_awaited_once_with(result.id, content.file)
        thumbnailer.generate_thumbnails_async.assert_awaited_once_with(
            result.id, sizes=[64, 512, 2304]
        )

        owner_id = ns_service.get_by_path.return_value.owner_id
        user_service.get_account.assert_awaited_once_with(owner_id)
        ns_service.get_space_used_by_owner_id.assert_awaited_once_with(owner_id)
        audit_trail.file_added.assert_called_once_with(result)

    async def test_when_adding_to_trash_folder(
        self, ns_use_case: NamespaceUseCase, content: IFileContent
    ):
        ns_path, path = "admin", "Trash/f.txt"
        with pytest.raises(File.MalformedPath):
            await ns_use_case.add_file(ns_path, path, content)

    async def test_when_max_upload_size_limit_is_exceeded(
        self, ns_use_case: NamespaceUseCase, content: IFileContent
    ):
        ns_path, path = "admin", "f.txt"
        with (
            mock.patch.object(config.features, "upload_file_max_size", 5),
            pytest.raises(File.TooLarge),
        ):
            await ns_use_case.add_file(ns_path, path, content)

    async def test_when_exceeding_storage_quota_limit(
        self, ns_use_case: NamespaceUseCase, content: IFileContent
    ):
        # GIVEN
        audit_trail = cast(mock.MagicMock, ns_use_case.audit_trail)
        file_service = cast(mock.MagicMock, ns_use_case.file)
        dupefinder = cast(mock.MagicMock, ns_use_case.dupefinder)
        metadata = cast(mock.MagicMock, ns_use_case.metadata)
        ns_service = cast(mock.MagicMock, ns_use_case.namespace)
        ns_service.get_space_used_by_owner_id = mock.AsyncMock(return_value=1024)
        thumbnailer = cast(mock.MagicMock, ns_use_case.thumbnailer)
        user_service = cast(mock.MagicMock, ns_use_case.user)
        user_service.get_account.return_value = _make_account(storage_quota=1024)

        ns_path, path = "admin", "f.txt"
        # WHEN
        with pytest.raises(Account.StorageQuotaExceeded):
            await ns_use_case.add_file(ns_path, path, content)

        # THEN
        file_service.create_file.assert_not_awaited()
        dupefinder.track.assert_not_awaited()
        metadata.track.assert_not_awaited()
        thumbnailer.generate_thumbnails_async.assert_not_awaited()

        owner_id = ns_service.get_by_path.return_value.owner_id
        user_service.get_account.assert_awaited_once_with(owner_id)
        ns_service.get_space_used_by_owner_id.assert_awaited_once_with(owner_id)
        audit_trail.file_added.assert_not_called()


class TestCreateFolder:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        audit_trail = cast(mock.MagicMock, ns_use_case.audit_trail)
        file_service = cast(mock.MagicMock, ns_use_case.file)
        # WHEN
        result = await ns_use_case.create_folder(ns_path, path)
        # THEN
        assert result == file_service.create_folder.return_value
        file_service.create_folder.assert_awaited_once_with(ns_path, path)
        audit_trail.folder_created.assert_called_once_with(result)


class TestDeleteItem:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        file_service = cast(mock.MagicMock, ns_use_case.file)
        # WHEN
        await ns_use_case.delete_item(ns_path, path)
        # THEN
        file_service.delete.assert_awaited_once_with(ns_path, path)

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
        file_service = cast(mock.MagicMock, ns_use_case.file)
        # WHEN
        result = await ns_use_case.download(ns_path, path)
        # THEN
        assert result == file_service.download.return_value
        file_service.download.assert_awaited_once_with(ns_path, path)


class TestDownloadByID:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        file_id = uuid.uuid4()
        file, chunks = mock.MagicMock(), mock.MagicMock()
        file_service = cast(mock.MagicMock, ns_use_case.file)
        file_service.download_by_id.return_value = file, chunks
        # WHEN
        result = await ns_use_case.download_by_id(file_id)
        # THEN
        assert result == chunks
        file_service.download_by_id.assert_awaited_once_with(file_id)


class TestDownloadFolder:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        file_service = cast(mock.MagicMock, ns_use_case.file)
        # WHEN
        result = ns_use_case.download_folder(ns_path, path)
        # THEN
        assert result == file_service.download_folder.return_value
        file_service.download_folder.assert_called_once_with(ns_path, path)


class TestEmptyTrash:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path = "admin"
        audit_trail = cast(mock.MagicMock, ns_use_case.audit_trail)
        file_service = cast(mock.MagicMock, ns_use_case.file)
        # WHEN
        await ns_use_case.empty_trash(ns_path)
        # THEN
        file_service.empty_folder.assert_awaited_once_with(ns_path, "trash")
        audit_trail.trash_emptied.assert_called_once_with()


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
        file_service = cast(mock.MagicMock, ns_use_case.file)
        file_service.get_by_id_batch.return_value = files
        # WHEN
        duplicates = await ns_use_case.find_duplicates(ns_path, ".")
        # THEN
        assert duplicates == [[files[0], files[2]], [files[1], files[3]]]
        dupefinder.find_in_folder.assert_awaited_once_with(ns_path, ".", 5)
        file_service.get_by_id_batch.assert_awaited_once()

    async def test_when_no_duplicates(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path = "admin"
        dupefinder = cast(mock.MagicMock, ns_use_case.dupefinder)
        dupefinder.find_in_folder.return_value = []
        file_service = cast(mock.MagicMock, ns_use_case.file)
        file_service.get_by_id_batch.return_value = []
        # WHEN
        duplicates = await ns_use_case.find_duplicates(ns_path, ".")
        # THEN
        assert duplicates == []
        dupefinder.find_in_folder.assert_awaited_once_with(ns_path, ".", 5)
        file_service.get_by_id_batch.assert_awaited_once()


class TestGetFileMetadata:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path, file_id = "admin", uuid.uuid4()
        file_service = cast(mock.MagicMock, ns_use_case.file)
        metadata = cast(mock.MagicMock, ns_use_case.metadata)
        # WHEN
        result = await ns_use_case.get_file_metadata(ns_path, file_id)
        # THEN
        assert result == metadata.get_by_file_id.return_value
        file_service.get_by_id.assert_awaited_once_with(ns_path, file_id)
        file = file_service.get_by_id.return_value
        metadata.get_by_file_id.assert_awaited_once_with(file.id)


class TestGetFileThumbnail:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path, path = "admin", "img.jpeg"
        file = _make_file(ns_path, path)
        file_service = cast(mock.MagicMock, ns_use_case.file)
        file_service.get_by_id.return_value = file
        thumbnailer = cast(mock.MagicMock, ns_use_case.thumbnailer)
        thumbnail = thumbnailer.thumbnail.return_value
        # WHEN
        result = await ns_use_case.get_file_thumbnail(ns_path, file.id, size=32)
        # THEN
        assert result == (file, thumbnail)
        file_service.get_by_id.assert_awaited_once_with(ns_path, file.id)
        thumbnailer.thumbnail.assert_awaited_once_with(file.id, file.chash, 32)


class TestGetItemAtPath:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        file_service = cast(mock.MagicMock, ns_use_case.file)
        # WHEN
        result = await ns_use_case.get_item_at_path(ns_path, path)
        # THEN
        assert result == file_service.get_at_path.return_value
        file_service.get_at_path.assert_called_once_with(ns_path, path)


class TestListFolder:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path, path = "admin", "home"
        file_service = cast(mock.MagicMock, ns_use_case.file)
        # WHEN
        result = await ns_use_case.list_folder(ns_path, path)
        # THEN
        assert result == file_service.list_folder.return_value
        file_service.list_folder.assert_awaited_once_with(ns_path, path)

    async def test_list_root_folder(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path, path = "admin", "."
        file_service = cast(mock.MagicMock, ns_use_case.file)
        file_service.list_folder.return_value = [
            _make_file(ns_path, "."),
            _make_file(ns_path, "trash"),
            _make_file(ns_path, "home"),
        ]
        # WHEN
        result = await ns_use_case.list_folder(ns_path, path)
        # THEN
        assert result == [file_service.list_folder.return_value[-1]]
        file_service.list_folder.assert_awaited_once_with(ns_path, path)


class TestMoveItem:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_path, at_path, to_path = "admin", "a/b", "a/c"
        audit_trail = cast(mock.MagicMock, ns_use_case.audit_trail)
        file_service = cast(mock.MagicMock, ns_use_case.file)
        # WHEN
        result = await ns_use_case.move_item(ns_path, at_path, to_path)
        # THEN
        assert result == file_service.move.return_value
        file_service.move.assert_awaited_once_with(ns_path, at_path, to_path)
        audit_trail.file_moved.assert_called_once_with(result)

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
        ns_path, path, next_path = "admin", "f.txt", Path("Trash/f.txt")
        audit_trail = cast(mock.MagicMock, ns_use_case.audit_trail)
        file_service = cast(mock.MagicMock, ns_use_case.file)
        file_service.exists_at_path.return_value = False
        # WHEN
        result = await ns_use_case.move_item_to_trash(ns_path, path)
        # THEN
        assert result == file_service.move.return_value
        file_service.exists_at_path.assert_awaited_once_with(ns_path, next_path)
        file_service.move.assert_awaited_once_with(ns_path, path, next_path)
        audit_trail.file_trashed.assert_called_once_with(result)

    @mock.patch("app.toolkit.timezone.now", return_value=datetime(2000, 1, 1, 19, 37))
    async def test_when_path_at_trash_exists(
        self, tz_now: MagicMock, ns_use_case: NamespaceUseCase
    ):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        next_path = Path("Trash/f 193700000000.txt")
        file_service = cast(mock.MagicMock, ns_use_case.file)
        file_service.exists_at_path.return_value = True
        # WHEN
        await ns_use_case.move_item_to_trash(ns_path, path)
        # THEN
        tz_now.assert_called_once_with()
        file_service.exists_at_path.assert_awaited_once_with(
            ns_path, Path("Trash/f.txt")
        )
        file_service.move.assert_awaited_once_with(ns_path, path, next_path)


class TestReindex:
    async def test(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_service = cast(mock.MagicMock, ns_use_case.namespace)
        file_service = cast(mock.MagicMock, ns_use_case.file)
        # WHEN
        await ns_use_case.reindex("admin")
        # THEN
        ns_service.get_by_path.assert_awaited_once_with("admin")
        file_service.reindex.assert_awaited_once_with("admin", ".")
        file_service.filecore.create_folder.assert_awaited_once_with("admin", "Trash")

    async def test_when_trash_folder_was_created(self, ns_use_case: NamespaceUseCase):
        # GIVEN
        ns_service = cast(mock.MagicMock, ns_use_case.namespace)
        file_service = cast(mock.MagicMock, ns_use_case.file)
        file_service.filecore.create_folder.side_effect = File.AlreadyExists
        # WHEN
        await ns_use_case.reindex("admin")
        # THEN
        ns_service.get_by_path.assert_awaited_once_with("admin")
        file_service.reindex.assert_awaited_once_with("admin", ".")
        file_service.filecore.create_folder.assert_awaited_once_with("admin", "Trash")


class TestReindexContents:
    async def test(self, ns_use_case: NamespaceUseCase, image_content: IFileContent):
        # GIVEN
        ns_path = "admin"
        jpg_1 = _make_file(ns_path, "a/b/img (1).jpeg")
        jpg_2 = _make_file(ns_path, "a/b/img (2).jpeg")

        async def iter_by_mediatypes_result():
            yield [jpg_1]
            yield [jpg_2]

        file_service = cast(mock.MagicMock, ns_use_case.file)
        filecore = file_service.filecore
        filecore.iter_by_mediatypes.return_value = iter_by_mediatypes_result()
        filecore.download.side_effect = [
            (jpg_1, _aiter(image_content.file)),
            (jpg_2, _aiter(image_content.file)),
        ]
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
