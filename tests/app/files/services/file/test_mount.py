from __future__ import annotations

from typing import cast
from unittest import mock

import pytest

from app.app.files.domain import MountPoint, Path
from app.app.files.domain.file import FullyQualifiedPath
from app.app.files.repositories import IMountRepository
from app.app.files.services.file.mount import MountService

pytestmark = [pytest.mark.asyncio]


@pytest.fixture
def mount_service():
    database = mock.MagicMock(mount=mock.AsyncMock(IMountRepository))
    return MountService(database=database)


class TestGetClosesBySource:
    async def test(self, mount_service: MountService):
        # GIVEN
        ns_path = "admin"
        mount_point = MountPoint(
            source=MountPoint.Source(
                ns_path="user",
                path=Path("SharedFolder"),
            ),
            folder=MountPoint.ContainingFolder(
                ns_path="admin",
                path=Path("Folder"),
            ),
            display_name="MountedFolder",
        )
        db = cast(mock.AsyncMock, mount_service.db)
        db.mount.get_closest_by_source.return_value = mount_point
        # WHEN
        result = await mount_service.get_closest_by_source(
            mount_point.source.ns_path, mount_point.source.path, ns_path
        )
        # THEN
        db.mount.get_closest_by_source.assert_awaited_once_with(
            source_ns_path=mount_point.source.ns_path,
            source_path=mount_point.source.path,
            target_ns_path=ns_path,
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


class TestResolvePath:
    async def test(self, mount_service: MountService):
        # GIVEN
        ns_path, path = "admin", "Folder/MountedFolder"
        mount_point = MountPoint(
            source=MountPoint.Source(
                ns_path="user",
                path=Path("SharedFolder"),
            ),
            folder=MountPoint.ContainingFolder(
                ns_path="admin",
                path=Path("Folder"),
            ),
            display_name="MountedFolder",
        )
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
