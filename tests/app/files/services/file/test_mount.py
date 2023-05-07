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


class TestResolvePath:
    async def test(self, mount_service: MountService):
        # GIVEN
        ns_path, path = "admin", "Folder/MountedFolder"
        expected_mount_point = MountPoint(
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
        db.mount.get_closest.return_value = expected_mount_point
        # WHEN
        result = await mount_service.resolve_path(ns_path, path)
        # THEN
        db.mount.get_closest.assert_awaited_once_with(ns_path, path)
        assert result == FullyQualifiedPath(
            ns_path="user",
            path=Path("SharedFolder"),
            mount_point=expected_mount_point,
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
