from __future__ import annotations

import uuid
from io import BytesIO
from typing import IO, TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.files.domain import File, FullyQualifiedPath, MountedFile, MountPoint, Path
from app.app.files.services.file.file import _make_thumbnail_ttl, _resolve_file
from app.app.infrastructure.storage import ContentReader
from app.cache import disk_cache

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.files.domain import AnyPath
    from app.app.files.services import FileService


def _make_file(
    ns_path: str, path: AnyPath, size: int = 10, mediatype: str = "plain/text"
) -> File:
    return File(
        id=uuid.uuid4(),
        ns_path=ns_path,
        name=Path(path).name,
        path=path,
        size=size,
        mediatype=mediatype,
    )


def _make_mounted_file(source_file: File, ns_path: str, path: AnyPath) -> MountedFile:
    path = Path(path)
    return MountedFile(
            id=source_file.id,
            ns_path=ns_path,
            name=path.name,
            path=path,
            size=10,
            mediatype="plain/text",
            mount_point=MountPoint(
                source=MountPoint.Source(
                    ns_path=source_file.ns_path,
                    path=source_file.path,
                ),
                folder=MountPoint.ContainingFolder(
                    ns_path=ns_path,
                    path=path.parent,
                ),
                display_name=path.name,
            ),
        )


class TestResolveFile:
    def test_regular_file(self):
        # GIVEN
        file = _make_file("admin", "f.txt")
        fq_path = FullyQualifiedPath("admin", Path("f.txt"))
        # WHEN
        result = _resolve_file(file, fq_path.mount_point)
        # THEN
        assert result is file

    def test_mounted_file(self):
        # GIVEN
        source = _make_file("user", "Folder/SharedFolder")
        file = _make_mounted_file(source, " admin", "Sharing/TeamFolder/f.txt")
        fq_path = FullyQualifiedPath(
            ns_path="user",
            path=Path("Folder/SharedFolder/f.txt"),
            mount_point=file.mount_point,
        )
        # WHEN
        result = _resolve_file(file, fq_path.mount_point)
        # THEN
        assert result is file

    def test_path_that_is_a_mount_point(self):
        # GIVEN: a `user:Folder/SharedFolder` mounted to `admin:Folder` as `TeamFolder`
        file = _make_file("user", "Folder/SharedFolder")
        fq_path = FullyQualifiedPath(
            ns_path="user",
            path=Path("Folder/SharedFolder"),
            mount_point=MountPoint(
                source=MountPoint.Source(
                    ns_path="user",
                    path=Path("Folder/SharedFolder"),
                ),
                folder=MountPoint.ContainingFolder(
                    ns_path="admin",
                    path=Path("Sharing"),
                ),
                display_name="TeamFolder",
            ),
        )
        # WHEN
        result = _resolve_file(file, fq_path.mount_point)
        # THEN
        assert result == MountedFile(
            id=file.id,
            name="TeamFolder",
            ns_path="admin",
            path="Sharing/TeamFolder",
            size=file.size,
            mediatype=file.mediatype,
            mtime=file.mtime,
            mount_point=fq_path.mount_point,
        )

    @pytest.mark.parametrize("path", [
        Path("Folder/SharedFolder/InnerFolder"),
        Path("Folder/SharedFolder/InnerFolder/f.txt")
    ])
    def test_path_that_is_inside_mount_point(self, path: Path):
        # GIVEN: a `user:Folder/SharedFolder` mounted to `admin:Folder` as `TeamFolder`
        #
        file = _make_file("user", "Folder/SharedFolder/InnerFolder/f.txt")
        fq_path = FullyQualifiedPath(
            ns_path="user",
            path=path,
            mount_point=MountPoint(
                source=MountPoint.Source(
                    ns_path="user",
                    path=Path("Folder/SharedFolder"),
                ),
                folder=MountPoint.ContainingFolder(
                    ns_path="admin",
                    path=Path("Sharing"),
                ),
                display_name="TeamFolder",
            ),
        )
        # WHEN
        result = _resolve_file(file, fq_path.mount_point)
        # THEN
        assert result == MountedFile(
            id=file.id,
            name="f.txt",
            ns_path="admin",
            path="Sharing/TeamFolder/InnerFolder/f.txt",
            size=file.size,
            mediatype=file.mediatype,
            mtime=file.mtime,
            mount_point=fq_path.mount_point,
        )


@pytest.mark.asyncio
class TestCreateFile:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path, content = "admin", "f.txt", BytesIO(b"Dummy")
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        # WHEN
        result = await file_service.create_file(ns_path, path, content)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        file = filecore.create_file.return_value
        fq_path = mount_service.resolve_path.return_value
        assert result == _resolve_file(file, fq_path.mount_point)
        filecore.create_file.assert_called_once_with(
            fq_path.ns_path, fq_path.path, content
        )


@pytest.mark.asyncio
class TestCreateFolder:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        # WHEN
        result = await file_service.create_folder(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        file = filecore.create_folder.return_value
        fq_path = mount_service.resolve_path.return_value
        assert result == _resolve_file(file, fq_path.mount_point)
        filecore.create_folder.assert_called_once_with(fq_path.ns_path, fq_path.path)


@pytest.mark.asyncio
class TestDelete:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        fq_path = mount_service.resolve_path.return_value
        fq_path.is_mount_point = mock.MagicMock(return_value=False)
        # WHEN
        result = await file_service.delete(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        file = filecore.delete.return_value
        assert result == _resolve_file(file, fq_path.mount_point)
        filecore.delete.assert_called_once_with(fq_path.ns_path, fq_path.path)

    async def test_deleting_a_mount_point(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        fq_path = mount_service.resolve_path.return_value
        fq_path.is_mount_point = mock.MagicMock(return_value=True)
        # WHEN
        with pytest.raises(File.NotFound):
            await file_service.delete(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        filecore.delete.assert_not_called()


@pytest.mark.asyncio
class TestDownload:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        filecore = cast(mock.MagicMock, file_service.filecore)
        file, content = filecore.get_by_path.return_value, mock.MagicMock(ContentReader)
        filecore.download.return_value = file, content
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        # WHEN
        result = await file_service.download(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        fq_path = mount_service.resolve_path.return_value
        assert result == (_resolve_file(file, fq_path.mount_point), content)
        filecore.get_by_path.assert_called_once_with(fq_path.ns_path, fq_path.path)
        filecore.download.assert_called_once_with(filecore.get_by_path.return_value.id)


@pytest.mark.asyncio
class TestEmptyFolder:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", "folder"
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        # WHEN
        await file_service.empty_folder(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        fq_path = mount_service.resolve_path.return_value
        filecore.empty_folder.assert_called_once_with(fq_path.ns_path, fq_path.path)


@pytest.mark.asyncio
class TestGetAtPath:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        # WHEN
        result = await file_service.get_at_path(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        file = filecore.get_by_path.return_value
        fq_path = mount_service.resolve_path.return_value
        assert result == _resolve_file(file, fq_path.mount_point)
        filecore.get_by_path.assert_called_once_with(fq_path.ns_path, fq_path.path)


@pytest.mark.asyncio
class TestListFolder:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        filecore = cast(mock.AsyncMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        # WHEN
        await file_service.list_folder("admin", "f.txt")
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        fq_path = mount_service.resolve_path.return_value
        filecore.list_folder.assert_awaited_once_with(fq_path.ns_path, fq_path.path)


@pytest.mark.asyncio
class TestThumbnail:
    @mock.patch("app.app.files.services.file.file.thumbnails.thumbnail")
    async def test(
        self,
        thumbnail_mock: MagicMock,
        file_service: FileService,
        image_content: IO[bytes],
    ):
        # GIVEN
        file = _make_file("admin", "im.jpeg")
        filecore = cast(mock.AsyncMock, file_service.filecore)
        filecore.download.return_value = (
            file,
            ContentReader.from_iter(image_content, zipped=False),
        )
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        thumbnail_mock.return_value = b"dummy-image-content"
        # WHEN
        result = await file_service.thumbnail(file.ns_path, file.id, size=64)
        # THEN
        assert result == (file, thumbnail_mock.return_value)
        filecore.download.assert_awaited_once_with(file.id)
        mount_service.get_closest_by_source.assert_not_awaited()
        thumbnail_mock.assert_awaited_once()

    @mock.patch("app.app.files.services.file.file.thumbnails.thumbnail")
    async def test_mounted_file(
        self,
        thumbnail_mock: MagicMock,
        file_service: FileService,
        image_content: IO[bytes],
    ):
        # GIVEN
        source = _make_file("user", "Folder/SharedFolder/f.txt")
        file = _make_mounted_file(source, "admin", "Sharing/TeamFolder/f.txt")
        filecore = cast(mock.AsyncMock, file_service.filecore)
        filecore.download.return_value = (
            source,
            ContentReader.from_iter(image_content, zipped=False),
        )
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.get_closest_by_source.return_value = file.mount_point
        thumbnail_mock.return_value = b"dummy-image-content"
        # WHEN
        result = await file_service.thumbnail(file.ns_path, file.id, size=64)
        # THEN
        expected_file = _resolve_file(source, file.mount_point)
        assert result == (expected_file, thumbnail_mock.return_value)
        filecore.download.assert_awaited_once_with(source.id)
        mount_service.get_closest_by_source.assert_awaited_once_with(
            source.ns_path, source.path, target_ns_path=file.ns_path
        )
        thumbnail_mock.assert_awaited_once()

    @mock.patch("app.app.files.services.file.file.thumbnails.thumbnail")
    async def test_when_file_in_the_other_namespace(
        self,
        thumbnail_mock: MagicMock,
        file_service: FileService,
        image_content: IO[bytes],
    ):
        # GIVEN
        file = _make_file("user", "Folder/SharedFolder/f.txt")
        filecore = cast(mock.AsyncMock, file_service.filecore)
        filecore.download.return_value = (
            file,
            ContentReader.from_iter(image_content, zipped=False),
        )
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.get_closest_by_source.return_value = None
        thumbnail_mock.return_value = b"dummy-image-content"
        # WHEN
        with pytest.raises(File.NotFound):
            await file_service.thumbnail("admin", file.id, size=64)
        # THEN
        filecore.download.assert_awaited_once_with(file.id)
        mount_service.get_closest_by_source.assert_awaited_once_with(
            file.ns_path, file.path, target_ns_path="admin"
        )
        thumbnail_mock.assert_not_called()

    @mock.patch("app.app.files.services.file.file.thumbnails.thumbnail")
    async def test_cache_hits(
        self,
        thumbnail_mock: MagicMock,
        file_service: FileService,
        image_content: IO[bytes],
    ):
        # GIVEN
        file = _make_file("admin", "im.jpeg")
        filecore = cast(mock.AsyncMock, file_service.filecore)
        filecore.download.return_value = (
            file,
            ContentReader.from_iter(image_content, zipped=False),
        )
        thumbnail_mock.return_value = b"dummy-image-content"
        with disk_cache.detect as detector:
            # WHEN hits for the first time
            result1 = await file_service.thumbnail(file.ns_path, file.id, size=64)
            # THEN cache miss
            assert detector.calls == {}
            # WHEN hits for the second time
            result2 = await file_service.thumbnail(file.ns_path, file.id, size=64)
            # THEN cache hit
            call = [{'ttl': 604800, 'name': 'simple', 'template': '{file_id}:{size}'}]
            assert list(detector.calls.values()) == [call]
            assert result1 == result2
            filecore.download.assert_called_once_with(file.id)
            thumbnail_mock.assert_called_once()

    @pytest.mark.parametrize(["size", "ttl"], [
        (64, "7d"),
        (256, "24h")],
    )
    async def test_ttl_depends_on_size(self, size: int, ttl: str):
        assert _make_thumbnail_ttl(size=size) == ttl
