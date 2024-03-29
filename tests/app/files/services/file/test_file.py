from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.files.domain import File, FileMember, MountedFile, MountPoint, Path
from app.app.files.services.file.file import _resolve_file
from app.app.files.services.file.mount import FullyQualifiedPath

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.files.domain import AnyPath, IFileContent
    from app.app.files.domain.file_member import FileMemberActions
    from app.app.files.services import FileService


def _make_file(
    ns_path: str, path: AnyPath, size: int = 10, mediatype: str = "plain/text"
) -> File:
    path = Path(path)
    return File(
        id=uuid.uuid4(),
        ns_path=ns_path,
        name=path.name,
        path=path,
        chash=uuid.uuid4().hex,
        size=size,
        mediatype=mediatype,
    )


def _make_mounted_file(
    source_file: File,
    ns_path: str,
    path: AnyPath,
    actions: FileMemberActions | None = None,
) -> MountedFile:
    path = Path(path)
    return MountedFile(
            id=source_file.id,
            ns_path=ns_path,
            name=path.name,
            path=path,
            chash=uuid.uuid4().hex,
            size=10,
            modified_at=source_file.modified_at,
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
                actions=actions or FileMember.EDITOR,
            ),
        )


def _make_mount_point(
    source: File,
    mount_to: File,
    name: str | None = None,
    actions: FileMemberActions | None = None,
):
    return MountPoint(
        source=MountPoint.Source(
            ns_path=source.ns_path,
            path=source.path,
        ),
        folder=MountPoint.ContainingFolder(
            ns_path=mount_to.ns_path,
            path=mount_to.path,
        ),
        display_name=name or source.path.name,
        actions=actions or FileMember.EDITOR,
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
                actions=FileMember.EDITOR,
            ),
        )
        # WHEN
        result = _resolve_file(file, fq_path.mount_point)
        # THEN
        assert fq_path.mount_point is not None
        assert result == MountedFile(
            id=file.id,
            name="TeamFolder",
            ns_path="admin",
            path=Path("Sharing/TeamFolder"),
            chash=file.chash,
            size=file.size,
            mediatype=file.mediatype,
            modified_at=file.modified_at,
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
                actions=FileMember.EDITOR,
            ),
        )
        # WHEN
        result = _resolve_file(file, fq_path.mount_point)
        # THEN
        assert fq_path.mount_point is not None
        assert result == MountedFile(
            id=file.id,
            name="f.txt",
            ns_path="admin",
            path=Path("Sharing/TeamFolder/InnerFolder/f.txt"),
            chash=file.chash,
            size=file.size,
            mediatype=file.mediatype,
            modified_at=file.modified_at,
            mount_point=fq_path.mount_point,
        )


@pytest.mark.anyio
class TestCreateFile:
    @mock.patch("app.app.files.services.file.FileService.get_available_path")
    async def test(
        self,
        get_available_path_mock: MagicMock,
        file_service: FileService,
        content: IFileContent,
    ):
        # GIVEN
        ns_path, path, modified_at = "admin", Path("f.txt"), None
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.return_value = FullyQualifiedPath(ns_path, path)
        get_available_path_mock.return_value = path
        # WHEN
        result = await file_service.create_file(ns_path, path, content)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        file = filecore.create_file.return_value
        fq_path = mount_service.resolve_path.return_value
        assert result == _resolve_file(file, fq_path.mount_point)
        get_available_path_mock.assert_awaited_once_with(fq_path.ns_path, fq_path.path)
        filecore.create_file.assert_called_once_with(
            fq_path.ns_path, path, content, modified_at
        )

    async def test_when_not_allowed(
        self, file_service: FileService, content: IFileContent
    ):
        # GIVEN
        ns_path, path = "user", "teamfolder/f.txt"
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.return_value = FullyQualifiedPath(
            "admin",
            Path("folder/f.txt"),
            mount_point=_make_mount_point(
                source=_make_file("admin", "folder"),
                mount_to=_make_file("user", "."),
                name="teamfolder",
                actions=MountPoint.Actions(can_upload=False),
            ),
        )
        # WHEN
        with pytest.raises(File.ActionNotAllowed):
            await file_service.create_file(ns_path, path, content)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        filecore.create_file.assert_not_awaited()


@pytest.mark.anyio
class TestCreateFolder:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", Path("folder")
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.return_value = FullyQualifiedPath(ns_path, path)
        # WHEN
        result = await file_service.create_folder(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        file = filecore.create_folder.return_value
        fq_path = mount_service.resolve_path.return_value
        assert result == _resolve_file(file, fq_path.mount_point)
        filecore.create_folder.assert_called_once_with(fq_path.ns_path, fq_path.path)

    async def test_when_not_allowed(self, file_service: FileService):
        # GIVEN
        ns_path, path = "user", "teamfolder/folder"
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.return_value = FullyQualifiedPath(
            "admin",
            Path("folder/folder"),
            mount_point=_make_mount_point(
                source=_make_file("admin", "folder"),
                mount_to=_make_file("user", "."),
                name="teamfolder",
                actions=MountPoint.Actions(can_upload=False),
            ),
        )
        # WHEN
        with pytest.raises(File.ActionNotAllowed):
            await file_service.create_folder(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        filecore.create_folder.assert_not_awaited()


@pytest.mark.anyio
class TestDelete:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", Path("f.txt")
        filecore = cast(mock.MagicMock, file_service.filecore)
        fq_path = FullyQualifiedPath(ns_path, path)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.return_value = fq_path
        # WHEN
        result = await file_service.delete(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        file = filecore.delete.return_value
        assert result == _resolve_file(file, fq_path.mount_point)
        filecore.delete.assert_called_once_with(fq_path.ns_path, fq_path.path)

    async def test_when_not_allowed(self, file_service: FileService):
        # GIVEN
        ns_path, path = "user", "teamfolder/folder"
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.return_value = FullyQualifiedPath(
            "admin",
            Path("folder/folder"),
            mount_point=_make_mount_point(
                source=_make_file("admin", "folder"),
                mount_to=_make_file("user", "."),
                name="teamfolder",
                actions=MountPoint.Actions(can_delete=False),
            ),
        )
        # WHEN
        with pytest.raises(File.ActionNotAllowed):
            await file_service.delete(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        filecore.delete.assert_not_called()

    async def test_deleting_a_mount_point(self, file_service: FileService):
        # GIVEN
        ns_path, path = "user", "teamfolder"
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        fq_path = FullyQualifiedPath(
            "admin",
            Path("folder"),
            mount_point=_make_mount_point(
                source=_make_file("admin", "folder"),
                mount_to=_make_file("user", "."),
                name="teamfolder",
                actions=MountPoint.Actions(can_delete=True),
            ),
        )
        mount_service.resolve_path.return_value = fq_path
        # WHEN
        with pytest.raises(File.NotFound):
            await file_service.delete(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        filecore.delete.assert_not_called()


@pytest.mark.anyio
class TestDownload:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", Path("f.txt")
        filecore = cast(mock.MagicMock, file_service.filecore)
        file, content = filecore.get_by_path.return_value, mock.AsyncMock()
        filecore.download.return_value = file, content
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.return_value = FullyQualifiedPath(ns_path, path)
        # WHEN
        result = await file_service.download(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        fq_path = mount_service.resolve_path.return_value
        assert result == (_resolve_file(file, fq_path.mount_point), content)
        filecore.get_by_path.assert_called_once_with(fq_path.ns_path, fq_path.path)
        filecore.download.assert_called_once_with(filecore.get_by_path.return_value.id)

    async def test_when_not_allowed(self, file_service: FileService):
        # GIVEN
        ns_path, path = "user", "teamfolder/folder"
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.return_value = FullyQualifiedPath(
            "admin",
            Path("folder/folder"),
            mount_point=_make_mount_point(
                source=_make_file("admin", "folder"),
                mount_to=_make_file("user", "."),
                name="teamfolder",
                actions=MountPoint.Actions(can_download=False),
            ),
        )
        # WHEN
        with pytest.raises(File.ActionNotAllowed):
            await file_service.download(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        filecore.get_by_path.assert_not_awaited()
        filecore.download.assert_not_called()


@pytest.mark.anyio
class TestDownloadByID:
    async def test(self, file_service: FileService):
        # GIVEN
        file, content = _make_file("admin", "f.txt"), mock.AsyncMock()
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.download.return_value = file, content
        # WHEN
        result = await file_service.download_by_id(file.id)
        # THEN
        assert result == (file, content)
        filecore.download.assert_awaited_once_with(file.id)


class TestDownloadFolder:
    def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", Path("f.txt")
        filecore = cast(mock.MagicMock, file_service.filecore)
        # WHEN
        result = file_service.download_folder(ns_path, path)
        # THEN
        assert result == filecore.download_folder.return_value
        filecore.download_folder.assert_called_once_with(ns_path, path)


@pytest.mark.anyio
class TestEmptyFolder:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", Path("folder")
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.return_value = FullyQualifiedPath(ns_path, path)
        # WHEN
        await file_service.empty_folder(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        fq_path = mount_service.resolve_path.return_value
        filecore.empty_folder.assert_awaited_once_with(fq_path.ns_path, fq_path.path)

    async def test_when_not_allowed(self, file_service: FileService):
        # GIVEN
        ns_path, path = "user", "teamfolder/folder"
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.return_value = FullyQualifiedPath(
            "admin",
            Path("folder/folder"),
            mount_point=_make_mount_point(
                source=_make_file("admin", "folder"),
                mount_to=_make_file("user", "."),
                name="teamfolder",
                actions=MountPoint.Actions(can_delete=False),
            ),
        )
        # WHEN
        with pytest.raises(File.ActionNotAllowed):
            await file_service.empty_folder(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        filecore.empty_folder.assert_not_called()


@pytest.mark.anyio
class TestExistsAtPath:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", Path("folder")
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.return_value = FullyQualifiedPath(ns_path, path)
        # WHEN
        await file_service.exists_at_path(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        fq_path = mount_service.resolve_path.return_value
        filecore.exists_at_path.assert_awaited_once_with(fq_path.ns_path, fq_path.path)

    async def test_when_not_allowed(self, file_service: FileService):
        # GIVEN
        ns_path, path = "user", "teamfolder/folder"
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.return_value = FullyQualifiedPath(
            "admin",
            Path("folder/folder"),
            mount_point=_make_mount_point(
                source=_make_file("admin", "folder"),
                mount_to=_make_file("user", "."),
                name="teamfolder",
                actions=MountPoint.Actions(can_delete=False),
            ),
        )
        # WHEN
        with pytest.raises(File.ActionNotAllowed):
            await file_service.exists_at_path(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        filecore.exists_at_path.assert_not_called()


@pytest.mark.anyio
class TestGetAtPath:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", Path("f.txt")
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.return_value = FullyQualifiedPath(ns_path, path)
        # WHEN
        result = await file_service.get_at_path(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        file = filecore.get_by_path.return_value
        fq_path = mount_service.resolve_path.return_value
        assert result == _resolve_file(file, fq_path.mount_point)
        filecore.get_by_path.assert_called_once_with(fq_path.ns_path, fq_path.path)

    async def test_when_not_allowed(self, file_service: FileService):
        # GIVEN
        ns_path, path = "user", "teamfolder/folder"
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.return_value = FullyQualifiedPath(
            "admin",
            Path("folder/folder"),
            mount_point=_make_mount_point(
                source=_make_file("admin", "folder"),
                mount_to=_make_file("user", "."),
                name="teamfolder",
                actions=MountPoint.Actions(can_delete=False),
            ),
        )
        # WHEN
        with pytest.raises(File.ActionNotAllowed):
            await file_service.get_at_path(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        filecore.get_by_path.assert_not_called()


@pytest.mark.anyio
class TestGetAvailablePath:
    async def test_when_path_is_not_taken(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.get_available_path.return_value = path
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.get_available_path.return_value = path
        # WHEN
        result = await file_service.get_available_path(ns_path, path)
        # THEN
        assert result == path
        filecore.get_available_path.assert_awaited_once_with(ns_path, path)
        mount_service.get_available_path.assert_awaited_once_with(ns_path, path)

    async def test_when_path_is_taken_by_other_path(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.get_available_path.return_value = "f (1).txt"
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.get_available_path.return_value = path
        # WHEN
        result = await file_service.get_available_path(ns_path, path)
        # THEN
        assert result == "f (1).txt"
        filecore.get_available_path.assert_awaited_once_with(ns_path, path)
        mount_service.get_available_path.assert_awaited_once_with(ns_path, path)

    async def test_when_path_is_taken_by_mounted_path(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.get_available_path.return_value = path
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.get_available_path.return_value = "f (1).txt"
        # WHEN
        result = await file_service.get_available_path(ns_path, path)
        # THEN
        assert result == "f (1).txt"
        filecore.get_available_path.assert_awaited_once_with(ns_path, path)
        mount_service.get_available_path.assert_awaited_once_with(ns_path, path)

    async def test_when_path_is_taken(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.get_available_path.return_value = "f (2).txt"
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.get_available_path.return_value = "f (1).txt"
        # WHEN
        result = await file_service.get_available_path(ns_path, path)
        # THEN
        assert result == "f (2).txt"
        filecore.get_available_path.assert_awaited_once_with(ns_path, path)
        mount_service.get_available_path.assert_awaited_once_with(ns_path, path)


@pytest.mark.anyio
class TestGetByID:
    async def test(self, file_service: FileService):
        # GIVEN
        file = _make_file("admin", "f.txt")
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.get_by_id.return_value = file
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        # WHEN
        result = await file_service.get_by_id(file.ns_path, file.id)
        # THEN
        assert result == _resolve_file(file, None)
        filecore.get_by_id.assert_awaited_once_with(file.id)
        mount_service.get_closest_by_source.assert_not_called()

    async def test_getting_mounted_file(self, file_service: FileService):
        # GIVEN
        source = _make_file("admin", "folder/f.txt")
        file = _make_mounted_file(
            source,
            "folder",
            "TeamFolder/f.txt",
        )
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.get_by_id.return_value = file
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.get_closest_by_source.return_value = file.mount_point
        # WHEN
        result = await file_service.get_by_id("user", file.id)
        # THEN
        mount_point = mount_service.get_closest_by_source.return_value
        assert result == _resolve_file(file, mount_point)
        filecore.get_by_id.assert_awaited_once_with(file.id)
        mount_service.get_closest_by_source.assert_awaited_once_with(
            file.ns_path, file.path, target_ns_path="user"
        )

    async def test_getting_file_in_other_namespace(self, file_service: FileService):
        # GIVEN
        file = _make_file("admin", "f.txt")
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.get_by_id.return_value = file
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.get_closest_by_source.return_value = None
        # WHEN
        with pytest.raises(File.NotFound):
            await file_service.get_by_id("user", file.id)
        # THEN
        filecore.get_by_id.assert_called_once_with(file.id)
        mount_service.get_closest_by_source.assert_awaited_once_with(
            file.ns_path, file.path, target_ns_path="user"
        )

    async def test_when_not_allowed(self, file_service: FileService):
        # GIVEN
        source = _make_file("admin", "folder/f.txt")
        file = _make_mounted_file(
            source,
            "folder",
            "TeamFolder/f.txt",
            actions=MountPoint.Actions(can_view=False),
        )
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.get_by_id.return_value = file
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.get_closest_by_source.return_value = file.mount_point
        # WHEN
        with pytest.raises(File.ActionNotAllowed):
            await file_service.get_by_id("user", file.id)
        # THEN
        filecore.get_by_id.assert_awaited_once_with(file.id)
        mount_service.get_closest_by_source.assert_awaited_once_with(
            file.ns_path, file.path, target_ns_path="user"
        )


@pytest.mark.anyio
class TestGetByIDBatch:
    async def test(self, file_service: FileService):
        # GIVEN
        files = [_make_file("admin", "f.txt"), _make_file("admin", "f (1).txt")]
        file_ids = [file.id for file in files]
        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.get_by_id_batch.return_value = files
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.reverse_path_batch.return_value = {}
        # WHEN
        result = await file_service.get_by_id_batch("admin", ids=file_ids)
        # THEN
        assert result == files
        filecore.get_by_id_batch.assert_awaited_once_with(file_ids)
        mount_service.reverse_path_batch.assert_awaited_once_with("admin", sources=[])

    async def test_getting_mounted_files(self, file_service: FileService):
        # GIVEN
        files = [_make_file("admin", "f.txt"), _make_file("admin", "f (1).txt")]

        mount_points = [
            _make_mount_point(
                source=_make_file("user 1", "Folder"),
                mount_to=_make_file("admin", "."),
                name="User 1",
            ),
            _make_mount_point(
                source=_make_file("user 2", "im.jpeg"),
                mount_to=_make_file("admin", "User 2"),
            ),
            _make_mount_point(
                source=_make_file("user 3", "im (1).jpeg"),
                mount_to=_make_file("admin", "User 3"),
                actions=MountPoint.Actions(can_view=False),
            ),
        ]
        shared_files = [
            _make_file("user 1", "Folder/user.txt"),
            _make_file("user 2", "im.jpeg"),
            _make_file("user 3", "im (1).jpeg"),
        ]

        filecore = cast(mock.MagicMock, file_service.filecore)
        filecore.get_by_id_batch.return_value = files + shared_files

        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.reverse_path_batch.return_value = {
            (shared_files[0].ns_path, shared_files[0].path): FullyQualifiedPath(
                ns_path=shared_files[0].ns_path,
                path=shared_files[0].path,
                mount_point=mount_points[0],
            ),
            (shared_files[1].ns_path, shared_files[1].path): FullyQualifiedPath(
                ns_path=shared_files[1].ns_path,
                path=shared_files[1].path,
                mount_point=mount_points[1],
            ),
        }

        file_ids = [file.id for file in files] + [file.id for file in shared_files]

        # WHEN
        result = await file_service.get_by_id_batch("admin", ids=file_ids)

        # THEN
        assert result == [
            files[0],
            files[1],
            _resolve_file(shared_files[0], mount_points[0]),
            _resolve_file(shared_files[1], mount_points[1]),
        ]
        filecore.get_by_id_batch.assert_awaited_once_with(file_ids)
        mount_service.reverse_path_batch.assert_awaited_once_with(
            "admin",
            sources=[
                ("user 1", Path("Folder/user.txt")),
                ("user 2", Path("im.jpeg")),
                ("user 3", Path("im (1).jpeg")),
            ]
        )


@pytest.mark.anyio
class TestListFolder:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", Path("folder")
        filecore = cast(mock.AsyncMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.return_value = FullyQualifiedPath(ns_path, path)
        # WHEN
        await file_service.list_folder(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        fq_path = mount_service.resolve_path.return_value
        filecore.list_folder.assert_awaited_once_with(fq_path.ns_path, fq_path.path)

    async def test_when_not_allowed(self, file_service: FileService):
        # GIVEN
        ns_path, path = "user", "teamfolder/folder"
        filecore = cast(mock.MagicMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.return_value = FullyQualifiedPath(
            "admin",
            Path("folder/folder"),
            mount_point=_make_mount_point(
                source=_make_file("admin", "folder"),
                mount_to=_make_file("user", "."),
                name="teamfolder",
                actions=MountPoint.Actions(can_view=False),
            ),
        )
        # WHEN
        with pytest.raises(File.ActionNotAllowed):
            await file_service.list_folder(ns_path, path)
        # THEN
        mount_service.resolve_path.assert_awaited_once_with(ns_path, path)
        filecore.list_folder.assert_not_awaited()


@pytest.mark.anyio
class TestMount:
    async def test(self, file_service: FileService):
        # GIVEN
        file = _make_file("admin", "f.txt")

        at_folder = ("user", "folder")
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        fq_path = FullyQualifiedPath(ns_path="user", path=Path("folder"))
        mount_service.resolve_path.return_value = fq_path

        filecore = cast(mock.AsyncMock, file_service.filecore)
        filecore.get_by_id.return_value = file

        target, attr = file_service.__class__, "get_available_path"
        with mock.patch.object(target, attr) as get_available_path_mock:
            get_available_path_mock.return_value = Path("folder/f (1).txt")
            # WHEN
            await file_service.mount(file.id, at_folder=at_folder)

        # THEN
        mount_service.resolve_path.assert_awaited_once_with(*at_folder)
        filecore.get_by_id.assert_awaited_once_with(file.id)
        file = filecore.get_by_id.return_value
        get_available_path_mock.assert_awaited_once_with("user", Path("folder/f.txt"))
        mount_service.create.assert_awaited_once_with(
            source=(file.ns_path, file.path),
            at_folder=at_folder,
            name="f (1).txt",
        )

    async def test_when_mounting_inside_mounted_folder(self, file_service: FileService):
        # GIVEN
        file = _make_file("admin", "f.txt")

        at_folder = ("user", "folder")
        mount_point = _make_mount_point(
            source=_make_file("user_b", "folder"),
            mount_to=_make_file("user", "."),
        )
        fq_path = FullyQualifiedPath(
            ns_path="admin", path=Path("folder"), mount_point=mount_point
        )

        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.return_value = fq_path
        filecore = cast(mock.AsyncMock, file_service.filecore)

        # WHEN
        with pytest.raises(File.IsMounted):
            await file_service.mount(file.id, at_folder=at_folder)

        # THEN
        mount_service.resolve_path.assert_awaited_once_with(*at_folder)
        filecore.get_by_id.assert_not_called()
        filecore.exists_at_path.assert_not_called()
        mount_service.assert_not_called()

    async def test_when_parent_folder_does_not_exist(self, file_service: FileService):
        # GIVEN
        file = _make_file("admin", "f.txt")

        at_folder = ("user", "folder")
        fq_path = FullyQualifiedPath(ns_path="user", path=Path("folder"))

        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.return_value = fq_path

        filecore = cast(mock.AsyncMock, file_service.filecore)
        filecore.exists_at_path.return_value = False

        # WHEN
        with pytest.raises(File.MissingParent):
            await file_service.mount(file.id, at_folder=at_folder)

        # THEN
        mount_service.resolve_path.assert_awaited_once_with(*at_folder)
        filecore.exists_at_path.assert_awaited_once_with("user", Path("folder"))
        filecore.get_by_id.assert_not_called()
        mount_service.assert_not_called()

    async def test_when_mounting_in_the_same_namespace(self, file_service: FileService):
        # GIVEN
        file = _make_file("user", "f.txt")

        at_folder = ("user", "folder")
        fq_path = FullyQualifiedPath(ns_path="user", path=Path("folder"))

        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.return_value = fq_path

        filecore = cast(mock.AsyncMock, file_service.filecore)
        filecore.get_by_id.return_value = file
        filecore.exists_at_path.side_effect = [True, True]

        # WHEN
        with pytest.raises(File.MalformedPath):
            await file_service.mount(file.id, at_folder=at_folder)

        # THEN
        mount_service.resolve_path.assert_awaited_once_with(*at_folder)
        filecore.get_by_id.assert_awaited_once_with(file.id)
        file = filecore.get_by_id.return_value
        filecore.exists_at_path.assert_awaited_once_with("user", Path("folder"))
        mount_service.assert_not_called()


@pytest.mark.anyio
class TestMove:
    async def test_moving_regular_files(self, file_service: FileService):
        # GIVEN
        at_fq_path = FullyQualifiedPath(ns_path="admin", path=Path("f.txt"))
        to_fq_path = FullyQualifiedPath(ns_path="admin", path=Path("f (1).txt"))
        filecore = cast(mock.AsyncMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.side_effect = [at_fq_path, to_fq_path]
        # WHEN
        file = await file_service.move("admin", "f.txt", "f (1).txt")
        # THEN
        assert file == filecore.move.return_value
        mount_service.resolve_path.assert_has_awaits([
            mock.call(at_fq_path.ns_path, at_fq_path.path),
            mock.call(to_fq_path.ns_path, to_fq_path.path),
        ])
        mount_service.move.assert_not_awaited()
        filecore.move.assert_awaited_once_with(
            at=("admin", "f.txt"),
            to=("admin", "f (1).txt"),
        )

    async def test_renaming_a_mount_point(self, file_service: FileService):
        # GIVEN
        mount_point = _make_mount_point(
            _make_file("user", "Folder/SharedFolder"),
            mount_to=_make_file("admin", "Sharing"),
            name="TeamFolder",
        )
        at_fq_path = FullyQualifiedPath(
            ns_path="user",
            path=Path("Folder/SharedFolder"),
            mount_point=mount_point,
        )
        to_fq_path = FullyQualifiedPath(
            ns_path="user",
            path=Path("Folder/SharedFolder"),
            mount_point=mount_point,
        )
        filecore = cast(mock.AsyncMock, file_service.filecore)
        filecore.exists_at_path.return_value = False
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.side_effect = [at_fq_path, to_fq_path]
        # WHEN
        file = await file_service.move(
            "admin", "Sharing/TeamFolder", "Sharing/PublicFolder"
        )
        # THEN
        assert file == _resolve_file(
            filecore.get_by_path.return_value,
            mount_service.move.return_value,
        )
        mount_service.resolve_path.assert_has_awaits([
            mock.call("admin", "Sharing/TeamFolder"),
            mock.call("admin", "Sharing/PublicFolder"),
        ])
        filecore.exists_at_path.assert_awaited_once_with(
            to_fq_path.ns_path, to_fq_path.path
        )
        mount_service.move.assert_awaited_once_with(
            "admin", "Sharing/TeamFolder", "Sharing/PublicFolder"
        )
        filecore.move.assert_not_awaited()

    async def test_moving_a_mount_point(self, file_service: FileService):
        mount_point = _make_mount_point(
            _make_file("user", "Folder/SharedFolder"),
            mount_to=_make_file("admin", "Sharing"),
            name="TeamFolder",
        )
        at_fq_path = FullyQualifiedPath(
            ns_path="user",
            path=Path("Folder/SharedFolder"),
            mount_point=mount_point,
        )
        to_fq_path = FullyQualifiedPath(
            ns_path="admin",
            path=Path("Public/TeamFolder"),
        )
        filecore = cast(mock.AsyncMock, file_service.filecore)
        filecore.exists_at_path.return_value = False
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.side_effect = [at_fq_path, to_fq_path]
        # WHEN
        file = await file_service.move(
            "admin", "Sharing/TeamFolder", "Public/TeamFolder"
        )
        # THEN
        assert file == _resolve_file(
            filecore.get_by_path.return_value,
            mount_service.move.return_value,
        )
        filecore.exists_at_path.assert_awaited_once_with(
            to_fq_path.ns_path, to_fq_path.path
        )
        mount_service.resolve_path.assert_has_awaits([
            mock.call("admin", "Sharing/TeamFolder"),
            mock.call("admin", "Public/TeamFolder"),
        ])
        mount_service.move.assert_awaited_once_with(
            "admin", "Sharing/TeamFolder", "Public/TeamFolder"
        )
        mp = mount_service.move.return_value
        filecore.get_by_path.assert_awaited_once_with(mp.source.ns_path, mp.source.path)
        filecore.move.assert_not_awaited()

    async def test_when_not_allowed(self, file_service: FileService):
        # GIVEN
        mount_point = _make_mount_point(
            _make_file("user", "Folder/SharedFolder"),
            mount_to=_make_file("admin", "Sharing"),
            name="TeamFolder",
            actions=MountPoint.Actions(can_move=False),
        )
        at_fq_path = FullyQualifiedPath(
            ns_path="user",
            path=Path("Folder/SharedFolder"),
            mount_point=mount_point,
        )
        to_fq_path = FullyQualifiedPath(
            ns_path="user",
            path=Path("Folder/SharedFolder"),
            mount_point=mount_point,
        )
        filecore = cast(mock.AsyncMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.side_effect = [at_fq_path, to_fq_path]
        # WHEN
        with pytest.raises(File.ActionNotAllowed):
            await file_service.move(
                "admin", "Sharing/TeamFolder", "Sharing/PublicFolder"
            )
        # THEN
        mount_service.resolve_path.assert_has_awaits([
            mock.call("admin", "Sharing/TeamFolder"),
            mock.call("admin", "Sharing/PublicFolder"),
        ])
        filecore.exists_at_path.assert_not_awaited()
        mount_service.move.assert_not_awaited()
        filecore.move.assert_not_awaited()

    async def test_renaming_a_mount_point_when_file_with_the_same_name_exists(
        self, file_service: FileService
    ):
        # GIVEN
        mount_point = _make_mount_point(
            _make_file("user", "Folder/SharedFolder"),
            mount_to=_make_file("admin", "Sharing"),
            name="TeamFolder",
        )
        at_fq_path = FullyQualifiedPath(
            ns_path="user",
            path=Path("Folder/SharedFolder"),
            mount_point=mount_point,
        )
        to_fq_path = FullyQualifiedPath(
            ns_path="user",
            path=Path("Folder/SharedFolder"),
            mount_point=mount_point,
        )
        filecore = cast(mock.AsyncMock, file_service.filecore)
        filecore.exists_at_path.return_value = True
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.side_effect = [at_fq_path, to_fq_path]
        # WHEN
        with pytest.raises(File.AlreadyExists):
            await file_service.move(
                "admin", "Sharing/TeamFolder", "Sharing/PublicFolder"
            )
        # THEN
        mount_service.resolve_path.assert_has_awaits([
            mock.call("admin", "Sharing/TeamFolder"),
            mock.call("admin", "Sharing/PublicFolder"),
        ])
        filecore.exists_at_path.assert_awaited_once_with(
            to_fq_path.ns_path, to_fq_path.path
        )
        mount_service.move.assert_not_awaited()
        filecore.move.assert_not_awaited()

    async def test_renaming_a_file_when_mount_point_with_the_same_name_exists(
        self, file_service: FileService
    ):
        # GIVEN
        mount_point = _make_mount_point(
            _make_file("user", "Folder/SharedFolder"),
            mount_to=_make_file("admin", "Sharing"),
            name="TeamFolder",
        )
        at_fq_path = FullyQualifiedPath(
            ns_path="user",
            path=Path("Folder/SharedFolder"),
        )
        to_fq_path = FullyQualifiedPath(
            ns_path="user",
            path=Path("Folder/SharedFolder"),
            mount_point=mount_point,
        )
        filecore = cast(mock.AsyncMock, file_service.filecore)
        filecore.exists_at_path.return_value = False
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.side_effect = [at_fq_path, to_fq_path]
        # WHEN
        with pytest.raises(File.AlreadyExists):
            await file_service.move(
                "admin", "Sharing/TeamFolder", "Sharing/PublicFolder"
            )
        # THEN
        mount_service.resolve_path.assert_has_awaits([
            mock.call("admin", "Sharing/TeamFolder"),
            mock.call("admin", "Sharing/PublicFolder"),
        ])
        filecore.exists_at_path.assert_not_awaited()
        mount_service.move.assert_not_awaited()
        filecore.move.assert_not_awaited()

    async def test_moving_a_file_to_a_mount_point(self, file_service: FileService):
        # GIVEN
        mount_point = _make_mount_point(
            _make_file("user", "Folder/SharedFolder"),
            mount_to=_make_file("admin", "Sharing"),
            name="TeamFolder",
        )
        at_fq_path = FullyQualifiedPath(
            ns_path="admin",
            path=Path("f.txt"),
        )
        to_fq_path = FullyQualifiedPath(
            ns_path="user",
            path=Path("Folder/SharedFolder/f.txt"),
            mount_point=mount_point,
        )
        filecore = cast(mock.AsyncMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.side_effect = [at_fq_path, to_fq_path]
        # WHEN
        file = await file_service.move(
            "admin", "f.txt", "Sharing/TeamFolder/f.txt"
        )
        # THEN
        assert file == _resolve_file(
            filecore.move.return_value,
            to_fq_path.mount_point,
        )
        mount_service.resolve_path.assert_has_awaits([
            mock.call("admin", "f.txt"),
            mock.call("admin", "Sharing/TeamFolder/f.txt"),
        ])
        mount_service.move.assert_not_awaited()
        filecore.move.assert_awaited_once_with(
            at=("admin", "f.txt"),
            to=("user", "Folder/SharedFolder/f.txt"),
        )

    async def test_when_moving_between_mount_points(self, file_service: FileService):
        # GIVEN
        at_fq_path = FullyQualifiedPath(
            ns_path="user",
            path=Path("Folder/SharedFolder"),
            mount_point=_make_mount_point(
                _make_file("user", "Folder/SharedFolder"),
                mount_to=_make_file("admin", "Sharing"),
                name="TeamFolder"
            ),
        )
        to_fq_path = FullyQualifiedPath(
            ns_path="admin",
            path=Path("Folder/SharedFolder"),
            mount_point=_make_mount_point(
                _make_file("admin", "Folder/SharedFolder"),
                mount_to=_make_file("admin", "Sharing"),
                name="TeamFolder",
            )
        )
        filecore = cast(mock.AsyncMock, file_service.filecore)
        filecore.exists_at_path.return_value = True
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        mount_service.resolve_path.side_effect = [at_fq_path, to_fq_path]
        # WHEN
        with pytest.raises(File.MalformedPath) as excinfo:
            await file_service.move(
                "admin", "Sharing/TeamFolder", "Sharing/PublicFolder"
            )
        # THEN
        assert str(excinfo.value) == "Can't move between different mount points."
        mount_service.resolve_path.assert_has_awaits([
            mock.call("admin", "Sharing/TeamFolder"),
            mock.call("admin", "Sharing/PublicFolder"),
        ])
        mount_service.move.assert_not_awaited()
        filecore.move.assert_not_awaited()


@pytest.mark.anyio
class TestReindex:
    async def test(self, file_service: FileService):
        # GIVEN
        ns_path, path = "admin", "folder"
        filecore = cast(mock.AsyncMock, file_service.filecore)
        mount_service = cast(mock.AsyncMock, file_service.mount_service)
        # WHEN
        await file_service.reindex("admin", "folder")
        # THEN
        mount_service.resolve_path.assert_not_called()
        filecore.reindex.assert_awaited_once_with(ns_path, path)
