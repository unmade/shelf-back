from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.files.domain import File, FullyQualifiedPath, MountedFile, MountPoint, Path
from app.app.files.services.file.file import _resolve_file

if TYPE_CHECKING:
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


class TestResolvePath:
    def test_regular_file(self):
        # GIVEN
        file = _make_file("admin", "f.txt")
        fq_path = FullyQualifiedPath("admin", Path("f.txt"))
        # WHEN
        result = _resolve_file(file, fq_path)
        # THEN
        assert result is file

    def test_mounted_file(self):
        # GIVEN
        file = MountedFile(
            id=uuid.uuid4(),
            ns_path="admin",
            name="f.txt",
            path="Sharing/TeamFolder/f.txt",
            size=10,
            mediatype="plain/text",
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
        fq_path = FullyQualifiedPath(
            ns_path="user",
            path=Path("Folder/SharedFolder/f.txt"),
            mount_point=file.mount_point,
        )
        # WHEN
        result = _resolve_file(file, fq_path)
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
        result = _resolve_file(file, fq_path)
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
        result = _resolve_file(file, fq_path)
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
