from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.files.domain import File, Path

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.blobs.domain import IBlobContent
    from app.app.files.domain import AnyPath
    from app.app.files.services import FileService


def _make_file(
    ns_path: str,
    path: AnyPath,
    size: int = 10,
    mediatype: str = "plain/text",
) -> File:
    path = Path(path)
    return File(
        id=uuid.uuid7(),
        owner_id=uuid.uuid7(),
        ns_path=ns_path,
        name=path.name,
        path=path,
        chash=uuid.uuid4().hex,
        size=size,
        mediatype=mediatype,
    )


@pytest.mark.anyio
class TestCreateFile:
    @mock.patch("app.app.files.services.file.FileService.get_available_path")
    async def test(
        self,
        get_available_path_mock: MagicMock,
        file_service: FileService,
        content: IBlobContent,
    ):
        # GIVEN
        ns_path = "admin"
        path = Path("f.txt")
        file = _make_file(ns_path, path)
        filecore = cast(mock.MagicMock, file_service.filecore)
        get_available_path_mock.return_value = path
        filecore.create_file.return_value = file
        # WHEN
        result = await file_service.create_file(ns_path, path, content)
        # THEN
        get_available_path_mock.assert_awaited_once_with(ns_path, path)
        filecore.create_file.assert_awaited_once_with(ns_path, path, content, None)
        assert result == file


@pytest.mark.anyio
class TestCreateFolder:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path = "admin"
        path = Path("folder")
        file = _make_file(ns_path, path, mediatype="inode/directory")
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.create_folder.return_value = file
        # WHEN
        result = await file_service.create_folder(ns_path, path)
        # THEN
        filecore.create_folder.assert_awaited_once_with(ns_path, path)
        assert result == file


@pytest.mark.anyio
class TestDelete:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", Path("f.txt")
        file = _make_file(ns_path, path)
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.delete.return_value = file
        # WHEN
        result = await file_service.delete(ns_path, path)
        # THEN
        filecore.delete.assert_awaited_once_with(ns_path, path)
        assert result == file


@pytest.mark.anyio
class TestDownload:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", Path("f.txt")
        filecore = cast(mock.MagicMock, file_service.filecore)
        file, content = filecore.get_by_path.return_value, mock.AsyncMock()
        filecore.download.return_value = file, content
        # WHEN
        result = await file_service.download(ns_path, path)
        # THEN
        assert result == (file, content)
        filecore.get_by_path.assert_awaited_once_with(ns_path, path)
        filecore.download.assert_awaited_once_with(file.id)


@pytest.mark.anyio
class TestDownloadByID:
    async def test(self, file_service: FileService):
        # GIVEN
        file, content = _make_file("admin", "f.txt"), mock.AsyncMock()
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.download.return_value = (file, content)
        # WHEN
        result = await file_service.download_by_id(file.id)
        # THEN
        assert result == (file, content)
        filecore.download.assert_awaited_once_with(file.id)


class TestDownloadFolder:
    def test(self, file_service: FileService):
        # GIVEN
        owner_id, path = uuid.uuid7(), Path("f.txt")
        filecore = cast(mock.MagicMock, file_service.filecore)
        # WHEN
        result = file_service.download_folder(owner_id, path)
        # THEN
        assert result == filecore.download_folder.return_value
        filecore.download_folder.assert_called_once_with(owner_id, path)


@pytest.mark.anyio
class TestEmptyFolder:
    async def test_delegates_to_filecore(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", Path("folder")
        filecore = cast(mock.MagicMock, file_service.filecore)
        # WHEN
        await file_service.empty_folder(ns_path, path)
        # THEN
        filecore.empty_folder.assert_awaited_once_with(ns_path, path)


@pytest.mark.anyio
class TestExistsAtPath:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", Path("folder")
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.exists_at_path.return_value = True
        # WHEN
        result = await file_service.exists_at_path(ns_path, path)
        # THEN
        filecore.exists_at_path.assert_awaited_once_with(ns_path, path)
        assert result is True


@pytest.mark.anyio
class TestGetAtPath:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", Path("f.txt")
        filecore = cast(mock.MagicMock, file_service.filecore)
        file = _make_file(ns_path, path)
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.get_by_path.return_value = file
        # WHEN
        result = await file_service.get_at_path(ns_path, path)
        # THEN
        filecore.get_by_path.assert_awaited_once_with(ns_path, path)
        assert result == file


@pytest.mark.anyio
class TestGetAvailablePath:
    async def test_when_path_is_not_taken(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.get_available_path.return_value = path
        # WHEN
        result = await file_service.get_available_path(ns_path, path)
        # THEN
        assert result == path
        filecore.get_available_path.assert_awaited_once_with(ns_path, path)

    async def test_when_path_is_taken_by_other_path(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.get_available_path.return_value = "f (1).txt"
        # WHEN
        result = await file_service.get_available_path(ns_path, path)
        # THEN
        assert result == "f (1).txt"
        filecore.get_available_path.assert_awaited_once_with(ns_path, path)


@pytest.mark.anyio
class TestGetById:
    async def test(self, file_service: FileService):
        # GIVEN
        file = _make_file("admin", "f.txt")
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.get_by_id.return_value = file
        # WHEN
        result = await file_service.get_by_id(file.ns_path, file.id)
        # THEN
        assert result == file
        filecore.get_by_id.assert_awaited_once_with(file.id)

    async def test_getting_file_in_other_namespace(self, file_service: FileService):
        # GIVEN
        file = _make_file("admin", "f.txt")
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.get_by_id.return_value = file
        # WHEN
        with pytest.raises(File.NotFound):
            await file_service.get_by_id("user", file.id)
        # THEN
        filecore.get_by_id.assert_called_once_with(file.id)


@pytest.mark.anyio
class TestGetByIDBatch:
    async def test(self, file_service: FileService):
        # GIVEN
        files = [_make_file("admin", "f.txt"), _make_file("admin", "f (1).txt")]
        file_ids = [file.id for file in files]
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.get_by_id_batch.return_value = files
        # WHEN
        result = await file_service.get_by_id_batch("admin", ids=file_ids)
        # THEN
        assert result == files
        filecore.get_by_id_batch.assert_awaited_once_with(file_ids)


@pytest.mark.anyio
class TestListFolder:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", Path("folder")
        filecore = cast(mock.AsyncMock, file_service.filecore)
        # WHEN
        result = await file_service.list_folder(ns_path, path)
        # THEN
        assert result == filecore.list_folder.return_value
        filecore.list_folder.assert_awaited_once_with(ns_path, path)


@pytest.mark.anyio
class TestMove:
    async def test_moves_file_within_namespace(self, file_service: FileService):
        # GIVEN
        ns_path, at_path, to_path = "admin", "before.txt", "after.txt"
        filecore = cast(mock.MagicMock, file_service.filecore)
        # WHEN
        result = await file_service.move(ns_path, at_path, to_path)
        # THEN
        assert result == filecore.move.return_value
        filecore.move.assert_awaited_once_with(
            at=(ns_path, at_path),
            to=(ns_path, to_path),
        )
