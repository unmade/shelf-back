from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.app.files.domain import MountPoint
from app.app.files.repositories.mount import MountPointUpdate

if TYPE_CHECKING:
    from app.app.files.domain import Namespace
    from app.app.users.domain import User
    from app.infrastructure.database.edgedb.repositories import MountRepository
    from tests.infrastructure.database.edgedb.conftest import (
        FileMemberFactory,
        FolderFactory,
        MountFactory,
    )

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


class TestCountByPattern:
    async def test(
        self,
        mount_repo: MountRepository,
        folder_factory: FolderFactory,
        mount_factory: MountFactory,
        namespace_a: Namespace,
        namespace_b: Namespace,
    ):
        # GIVEN
        folder = await folder_factory(namespace_a.path, "Folder")

        shared_folder = await folder_factory(namespace_b.path)
        await mount_factory(shared_folder.id, folder.id, "Team Folder")

        max_folders = 3
        for idx in range(max_folders):
            shared_folder = await folder_factory(namespace_b.path)
            await mount_factory(shared_folder.id, folder.id, f"Team Folder ({idx})")

        # WHEN
        count = await mount_repo.count_by_name_pattern(
            namespace_a.path,
            folder.path,
            pattern="^Team Folder(\\s\\(\\d+\\))?$"
        )

        # THEN
        assert count == max_folders + 1

    async def test_when_no_match_exists(
        self, mount_repo: MountRepository, namespace: Namespace
    ):
        ns_path = namespace.path
        count = await mount_repo.count_by_name_pattern(
            ns_path,
            "Team Folder",
            "f\\s\\(\\d+\\).txt",
        )
        assert count == 0


class TestGetClosest:
    async def test(
        self,
        mount_repo: MountRepository,
        folder_factory: FolderFactory,
        mount_factory: MountFactory,
        namespace_a: Namespace,
        namespace_b: Namespace,
    ):
        # GIVEN
        folder = await folder_factory(namespace_a.path, "Folder")
        shared_folder = await folder_factory(namespace_b.path, "Shared Folder")
        await mount_factory(shared_folder.id, folder.id, "Team Folder")

        # WHEN: getting by exact path
        path = "Folder/Team Folder"
        mp_1 = await mount_repo.get_closest(namespace_a.path, path)

        # THEN
        assert mp_1.source.ns_path == shared_folder.ns_path
        assert mp_1.source.path == shared_folder.path
        assert mp_1.folder.ns_path == folder.ns_path
        assert mp_1.folder.path == folder.path

        # WHEN: getting by a path containing mount point
        path = "Folder/Team Folder/f.txt"
        mp_2 = await mount_repo.get_closest(namespace_a.path, path)

        # THEN
        assert mp_2 == mp_1

    async def test_when_mount_to_the_root_folder(
        self,
        mount_repo: MountRepository,
        folder_factory: FolderFactory,
        mount_factory: MountFactory,
        namespace_a: Namespace,
        namespace_b: Namespace,
    ):
        # GIVEN
        folder = await folder_factory(namespace_a.path, ".")
        shared_folder = await folder_factory(namespace_b.path, "Shared Folder")
        await mount_factory(shared_folder.id, folder.id, "Team Folder")

        # WHEN: getting by exact path
        with pytest.raises(MountPoint.NotFound):
            await mount_repo.get_closest(namespace_a.path, "Public/Team Folder")

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


class TestGetClosestBySource:
    async def test(
        self,
        mount_repo: MountRepository,
        folder_factory: FolderFactory,
        mount_factory: MountFactory,
        namespace_a: Namespace,
        namespace_b: Namespace,
    ):
        # GIVEN
        folder = await folder_factory(namespace_a.path, "Folder")
        shared_folder = await folder_factory(namespace_b.path, "Shared Folder")
        inner_folder = await folder_factory(namespace_b.path, "Shared Folder/Docs")
        await mount_factory(shared_folder.id, folder.id, "Team Folder")

        # WHEN: getting by exact path
        mp_1 = await mount_repo.get_closest_by_source(
            shared_folder.ns_path, shared_folder.path, namespace_a.path
        )

        # THEN
        assert mp_1.source.ns_path == shared_folder.ns_path
        assert mp_1.source.path == shared_folder.path
        assert mp_1.folder.ns_path == folder.ns_path
        assert mp_1.folder.path == folder.path

        # WHEN: getting by a path containing mount point
        mp_2 = await mount_repo.get_closest_by_source(
            inner_folder.ns_path, inner_folder.path, namespace_a.path
        )

        # THEN
        assert mp_2 == mp_1

    async def test_when_mount_does_not_exist(
        self,
        mount_repo: MountRepository,
        folder_factory: FolderFactory,
        namespace_a: Namespace,
        namespace_b: Namespace,
    ):
        # GIVEN
        inner_folder = await folder_factory(namespace_b.path, "Shared Folder/Docs")

        # WHEN / THEN
        with pytest.raises(MountPoint.NotFound):
            await mount_repo.get_closest_by_source(
                inner_folder.ns_path, inner_folder.path, namespace_a.path
            )


class TestListAll:
    async def test(
        self,
        mount_repo: MountRepository,
        folder_factory: FolderFactory,
        mount_factory: MountFactory,
        namespace_a: Namespace,
        namespace_b: Namespace,
    ):
        # GIVEN
        home = await folder_factory(namespace_a.path, ".")
        folder = await folder_factory(namespace_a.path, "Folder")
        shared_folder_1 = await folder_factory(namespace_b.path, "Shared Folder 1")
        shared_folder_2 = await folder_factory(namespace_b.path, "Shared Folder 2")
        await mount_factory(shared_folder_1.id, home.id, "Team Folder 1")
        await mount_factory(shared_folder_2.id, folder.id, "Team Folder 2")

        # WHEN
        mount_points = await mount_repo.list_all(namespace_a.path)

        # THEN
        assert mount_points == [
            MountPoint(
                source=MountPoint.Source(
                    ns_path=shared_folder_1.ns_path,
                    path=shared_folder_1.path,
                ),
                folder=MountPoint.ContainingFolder(
                    ns_path=home.ns_path,
                    path=home.path,
                ),
                display_name="Team Folder 1",
                actions=MountPoint.Actions(),
            ),
            MountPoint(
                source=MountPoint.Source(
                    ns_path=shared_folder_2.ns_path,
                    path=shared_folder_2.path,
                ),
                folder=MountPoint.ContainingFolder(
                    ns_path=folder.ns_path,
                    path=folder.path,
                ),
                display_name="Team Folder 2",
                actions=MountPoint.Actions(),
            ),
        ]

    async def test_when_no_mount_points_in_the_namespace(
        self,
        mount_repo: MountRepository,
        folder_factory: FolderFactory,
        mount_factory: MountFactory,
        namespace_a: Namespace,
        namespace_b: Namespace,
    ):
        # GIVEN
        folder = await folder_factory(namespace_a.path, "Folder")
        shared_folder = await folder_factory(namespace_b.path, "Shared Folder")
        await mount_factory(shared_folder.id, folder.id, "Team Folder")
        # WHEN
        mount_points = await mount_repo.list_all(namespace_b.path)
        # THEN
        assert mount_points == []


class TestSave:
    async def test(
        self,
        mount_repo: MountRepository,
        folder_factory: FolderFactory,
        file_member_factory: FileMemberFactory,
        namespace_a: Namespace,
        namespace_b: Namespace,
        user_a: User,
    ):
        # GIVEN
        folder = await folder_factory(namespace_a.path, "Folder")
        shared_folder = await folder_factory(namespace_b.path, "Shared Folder")
        await file_member_factory(shared_folder.id, user_a.id)
        mount_point = MountPoint(
            source=MountPoint.Source(
                ns_path=shared_folder.ns_path,
                path=shared_folder.path,
            ),
            folder=MountPoint.ContainingFolder(
                ns_path=folder.ns_path,
                path=folder.path,
            ),
            display_name="Public Folder",
            actions=MountPoint.Actions(),
        )
        # WHEN
        result = await mount_repo.save(mount_point)
        # THEN
        assert result is mount_point


class TestUpdate:
    async def test_updating_display_name(
        self,
        mount_repo: MountRepository,
        folder_factory: FolderFactory,
        mount_factory: MountFactory,
        namespace_a: Namespace,
        namespace_b: Namespace,
    ):
        # GIVEN
        folder = await folder_factory(namespace_a.path, "Folder")
        shared_folder = await folder_factory(namespace_b.path, "Shared Folder")
        mount_point = await mount_factory(shared_folder.id, folder.id, "Team Folder")

        # WHEN: getting by exact path
        fields = MountPointUpdate(folder=folder.path, display_name="Public Folder")
        updated_mp = await mount_repo.update(mount_point, fields=fields)

        # THEN
        assert updated_mp.folder.path == folder.path
        assert updated_mp.display_name == "Public Folder"

    async def test_updating_parent(
        self,
        mount_repo: MountRepository,
        folder_factory: FolderFactory,
        mount_factory: MountFactory,
        namespace_a: Namespace,
        namespace_b: Namespace,
    ):
        # GIVEN
        folder_1 = await folder_factory(namespace_a.path, "Folder 1")
        folder_2 = await folder_factory(namespace_a.path, "Folder 2")
        shared_folder = await folder_factory(namespace_b.path, "Shared Folder")
        mount_point = await mount_factory(shared_folder.id, folder_1.id, "Team Folder")

        # WHEN: getting by exact path
        fields = MountPointUpdate(folder=folder_2.path, display_name="Team Folder")
        updated_mp = await mount_repo.update(mount_point, fields=fields)

        # THEN
        assert updated_mp.folder.path == folder_2.path
        assert updated_mp.display_name == "Team Folder"
