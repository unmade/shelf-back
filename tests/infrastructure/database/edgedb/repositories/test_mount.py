from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.app.files.domain import MountPoint

if TYPE_CHECKING:
    from app.app.files.domain import Namespace
    from app.infrastructure.database.edgedb.repositories import MountRepository
    from tests.infrastructure.database.edgedb.conftest import (
        FolderFactory,
        MountFactory,
        NamespaceFactory,
        UserFactory,
    )

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


class TestGetClosest:
    async def test(
        self,
        mount_repo: MountRepository,
        user_factory: UserFactory,
        namespace_factory: NamespaceFactory,
        folder_factory: FolderFactory,
        mount_factory: MountFactory,
        namespace: Namespace,
    ):
        # GIVEN
        folder = await folder_factory(namespace.path, "Folder")

        user_b = await user_factory()
        namespace_b = await namespace_factory(user_b.username, owner_id=user_b.id)
        shared_folder = await folder_factory(namespace_b.path, "Shared Folder")

        await mount_factory(shared_folder.id, folder.id, "Team Folder")

        # WHEN: getting by exact path
        mount = await mount_repo.get_closest(namespace.path, "Folder/Team Folder")

        # THEN
        assert mount.source.ns_path == shared_folder.ns_path
        assert mount.source.path == shared_folder.path
        assert mount.folder.ns_path == folder.ns_path
        assert mount.folder.path == folder.path

        # WHEN: getting by a path containing mount point
        mp = await mount_repo.get_closest(namespace.path, "Folder/Team Folder/f.txt")

        # THEN
        assert mp == mount

    async def test_when_mount_does_not_exist(
        self,
        mount_repo: MountRepository,
        folder_factory: FolderFactory,
        namespace: Namespace
    ):
        # GIVEN
        await folder_factory(namespace.path, "Folder")

        # WHEN / THEN
        with pytest.raises(MountPoint.NotFound):
            await mount_repo.get_closest(namespace.path, "Folder/Team Folder")
