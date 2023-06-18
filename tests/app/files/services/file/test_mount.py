from __future__ import annotations

import uuid
from typing import cast
from unittest import mock

import pytest

from app.app.files.domain import File, MountPoint, Path
from app.app.files.domain.path import AnyPath
from app.app.files.repositories import IMountRepository
from app.app.files.repositories.mount import MountPointUpdate
from app.app.files.services.file import MountService
from app.app.files.services.file.mount import FullyQualifiedPath

pytestmark = [pytest.mark.asyncio]


def _make_file(ns_path: str, path: AnyPath, mediatype: str = "plain/text") -> File:
    return File(
        id=uuid.uuid4(),
        ns_path=ns_path,
        name=Path(path).name,
        path=path,
        size=10,
        mediatype=mediatype,
    )


def _make_folder(ns_path: str, path: AnyPath) -> File:
    return _make_file(ns_path, path, mediatype="application/directory")


def _make_mount_point(source: File, mount_to: File, name: str | None = None):
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
    )


@pytest.fixture
def mount_service():
    database = mock.MagicMock(mount=mock.AsyncMock(IMountRepository))
    return MountService(database=database)


class TestCreate:
    async def test(self, mount_service: MountService):
        # GIVEN
        mount_point = _make_mount_point(
            source=_make_file("admin", "f.txt"),
            mount_to=_make_file("user", "folder"),
            name="y.txt",
        )
        source, at_folder = mount_point.source, mount_point.folder
        db = cast(mock.AsyncMock, mount_service.db)
        # WHEN
        result = await mount_service.create(
            source=(source.ns_path, source.path),
            at_folder=(at_folder.ns_path, at_folder.path),
            name="y.txt",
        )
        # THEN
        assert result == db.mount.save.return_value
        db.mount.save.assert_awaited_once_with(mount_point)

    async def test_when_mounting_within_the_same_namespace(
        self, mount_service: MountService
    ):
        # GIVEN
        mount_point = _make_mount_point(
            source=_make_file("admin", "f.txt"),
            mount_to=_make_file("admin", "folder"),
            name="y.txt",
        )
        source, at_folder = mount_point.source, mount_point.folder
        db = cast(mock.AsyncMock, mount_service.db)
        # WHEN
        with pytest.raises(AssertionError) as excinfo:
            await mount_service.create(
                source=(source.ns_path, source.path),
                at_folder=(at_folder.ns_path, at_folder.path),
                name="y.txt",
            )
        # THEN
        assert str(excinfo.value) == "Can't mount within the same namespace."
        db.mount.save.assert_not_called()


class TestGetClosestBySource:
    async def test(self, mount_service: MountService):
        # GIVEN
        shared_folder = _make_file("user", "SharedFolder")
        folder = _make_file("admin", "Folder")
        mount_point = _make_mount_point(shared_folder, mount_to=folder, name="Public")
        db = cast(mock.AsyncMock, mount_service.db)
        db.mount.get_closest_by_source.return_value = mount_point
        # WHEN
        result = await mount_service.get_closest_by_source(
            mount_point.source.ns_path, mount_point.source.path, folder.ns_path
        )
        # THEN
        db.mount.get_closest_by_source.assert_awaited_once_with(
            source_ns_path=mount_point.source.ns_path,
            source_path=mount_point.source.path,
            target_ns_path=folder.ns_path,
        )
        assert result == mount_point

    async def test_when_mount_point_not_found(self, mount_service: MountService):
        # GIVEN
        db = cast(mock.AsyncMock, mount_service.db)
        db.mount.get_closest_by_source.side_effect = MountPoint.NotFound
        # WHEN
        result = await mount_service.get_closest_by_source(
            "user", "SharedFolder", target_ns_path="admin"
        )
        # THEN
        db.mount.get_closest_by_source.assert_awaited_once_with(
            source_ns_path="user",
            source_path="SharedFolder",
            target_ns_path="admin"
        )
        assert result is None


class TestGetAvailablePath:
    async def test(self, mount_service: MountService):
        # GIVEN
        ns_path, path = "admin", "Share/Team Folder/f.txt"
        db = cast(mock.AsyncMock, mount_service.db)
        db.mount.count_by_name_pattern.return_value = 2
        # WHEN
        result = await mount_service.get_available_path(ns_path, path)
        # THEN
        assert result == "Share/Team Folder/f (2).txt"
        db.mount.count_by_name_pattern.assert_called_once_with(
            ns_path, "Share/Team Folder", "^f(\\s\\(\\d+\\))?\\.txt$"
        )

    async def test_returning_path_as_is(self, mount_service: MountService):
        # GIVEN
        ns_path, path = "admin", "Share/Team Folder/f.txt"
        db = cast(mock.AsyncMock, mount_service.db)
        db.mount.count_by_name_pattern.return_value = 0
        # WHEN
        result = await mount_service.get_available_path(ns_path, path)
        # THEN
        assert result == path
        db.mount.count_by_name_pattern.assert_called_once_with(
            ns_path, "Share/Team Folder", "^f(\\s\\(\\d+\\))?\\.txt$"
        )

    async def test_name_is_escaped(self, mount_service: MountService):
        # GIVEN
        ns_path, path = "admin", "Share/f*\\s(1).txt"
        db = cast(mock.AsyncMock, mount_service.db)
        db.mount.count_by_name_pattern.return_value = 1
        # WHEN
        result = await mount_service.get_available_path(ns_path, path)
        # THEN
        assert result == "Share/f*\\s(1) (1).txt"
        db.mount.count_by_name_pattern.assert_called_once_with(
            ns_path, "Share", "^f\\*\\\\s\\(1\\)(\\s\\(\\d+\\))?\\.txt$"
        )


class TestMove:
    async def test(self, mount_service: MountService):
        # GIVEN
        ns_path, at_path, to_path = "admin", "shared", "public"
        db = cast(mock.AsyncMock, mount_service.db)
        # WHEN
        result = await mount_service.move(ns_path, at_path, to_path)
        # THEN
        assert result == db.mount.update.return_value
        db.mount.get_closest.assert_awaited_once_with(ns_path, at_path)
        mp = db.mount.get_closest.return_value
        db.mount.update.assert_awaited_once_with(
            mp,
            fields=MountPointUpdate(
                folder=".",
                display_name="public",
            ),
        )


class TestResolvePath:
    async def test(self, mount_service: MountService):
        # GIVEN
        shared_folder = _make_file("user", "SharedFolder")
        folder = _make_file("admin", "Folder")
        mount_point = _make_mount_point(shared_folder, mount_to=folder, name="Public")

        ns_path, path = "admin", "Folder/Public"

        db = cast(mock.AsyncMock, mount_service.db)
        db.mount.get_closest.return_value = mount_point
        # WHEN
        result = await mount_service.resolve_path(ns_path, path)
        # THEN
        db.mount.get_closest.assert_awaited_once_with(ns_path, path)
        assert result == FullyQualifiedPath(
            ns_path="user",
            path=Path("SharedFolder"),
            mount_point=mount_point,
        )

    async def test_when_mount_point_not_found(self, mount_service: MountService):
        # GIVEN
        ns_path, path = "admin", Path("Folder/MountedFolder")
        db = cast(mock.AsyncMock, mount_service.db)
        db.mount.get_closest.side_effect = MountPoint.NotFound
        # WHEN
        result = await mount_service.resolve_path(ns_path, path)
        # THEN
        db.mount.get_closest.assert_awaited_once_with(ns_path, path)
        assert result == FullyQualifiedPath(ns_path=ns_path, path=path)


class TestReversePathBatch:
    async def test(self, mount_service: MountService):
        # GIVEN
        shared_folder_1 = _make_folder("user", "SharedFolder 1")
        shared_folder_2 = _make_folder("user", "SharedFolder 2")
        folder_1 = _make_folder("admin", "Folder 1")
        folder_2 = _make_folder("admin", "Folder 2")

        mount_points = [
            _make_mount_point(shared_folder_1, mount_to=folder_1, name="Public Folder"),
            _make_mount_point(shared_folder_2, mount_to=folder_2)
        ]

        db = cast(mock.AsyncMock, mount_service.db)
        db.mount.list_all.return_value = mount_points

        # WHEN
        result = await mount_service.reverse_path_batch(
            "admin",
            sources=[
                ("user", "SharedFolder 1/f.txt"),
                ("user", Path("SharedFolder 2")),
                ("user", "SharedFolder"),
            ],
        )

        # THEN
        assert result == {
            ("user", "SharedFolder 1/f.txt"): FullyQualifiedPath(
                "user",
                Path("SharedFolder 1/f.txt"),
                mount_point=mount_points[0],
            ),
            ("user", Path("SharedFolder 2")): FullyQualifiedPath(
                "user",
                Path("SharedFolder 2"),
                mount_point=mount_points[1],
            ),
        }
        db.mount.list_all.assert_awaited_once_with("admin")

    async def test_when_sources_are_empty(self, mount_service: MountService):
        # GIVEN
        db = cast(mock.AsyncMock, mount_service.db)
        # WHEN
        result = await mount_service.reverse_path_batch("admin", sources=[])
        # THEN
        assert result == {}
        db.mount.list_all.assert_not_called()
