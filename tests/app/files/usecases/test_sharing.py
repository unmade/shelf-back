from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.files.domain import (
    File,
    FileMember,
    MountedFile,
    MountPoint,
    Namespace,
    Path,
    mediatypes,
)

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath
    from app.app.files.usecases import SharingUseCase

pytestmark = [pytest.mark.asyncio]


def _make_file(
    ns_path: str, path: AnyPath, size: int = 10, mediatype: str = "plain/text"
) -> File:
    path = Path(path)
    return File(
        id=uuid.uuid4(),
        ns_path=ns_path,
        name=path.name,
        path=path,
        size=size,
        mediatype=mediatype,
    )


def _make_folder(ns_path: str, path: AnyPath) -> File:
    return _make_file(ns_path, path, mediatype=mediatypes.FOLDER)


def _make_mounted_file(source_file: File, ns_path: str, path: AnyPath) -> MountedFile:
    path = Path(path)
    return MountedFile(
            id=source_file.id,
            ns_path=ns_path,
            name=path.name,
            path=path,
            size=10,
            mtime=source_file.mtime,
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
                actions=MountPoint.Actions(),
            ),
        )


class TestAddMember:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        file, username = _make_file("admin", "f.txt"), "user"
        user_service = cast(mock.MagicMock, sharing_use_case.user)
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        file_service.get_by_id.return_value = file
        file_member_service = cast(mock.MagicMock, sharing_use_case.file_member)
        # WHEN
        member = await sharing_use_case.add_member(file.ns_path, file.id, username)
        # THEN
        assert member == file_member_service.add.return_value
        file_service.get_by_id.assert_awaited_once_with(file.ns_path, file.id)
        user_service.get_by_username.assert_awaited_once_with(username)
        user = user_service.get_by_username.return_value
        file_member_service.add.assert_awaited_once_with(
            file.id, user.id, actions=FileMember.EDITOR
        )
        file_service.mount.assert_awaited_once_with(
            file.id, at_folder=(user.username, ".")
        )

    async def test_when_not_allowed(self, sharing_use_case: SharingUseCase):
        # GIVEN
        source_file = _make_folder("admin", "f.txt")
        file, username = _make_mounted_file(source_file, "user", "f.txt"), "member"
        user_service = cast(mock.MagicMock, sharing_use_case.user)
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        file_service.get_by_id.return_value = file
        file_member_service = cast(mock.MagicMock, sharing_use_case.file_member)
        # WHEN
        with pytest.raises(File.ActionNotAllowed):
            await sharing_use_case.add_member(file.ns_path, file.id, username)
        # THEN
        file_service.get_by_id.assert_awaited_once_with(file.ns_path, file.id)
        user_service.get_by_username.assert_not_awaited()
        file_member_service.add.assert_not_awaited()
        file_service.mount.assert_not_awaited()


class TestCreateLink:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        sharing_service = cast(mock.MagicMock, sharing_use_case.sharing)
        # WHEN
        link = await sharing_use_case.create_link(ns_path, path)
        # THEN
        file_service.get_at_path.assert_awaited_once_with(ns_path, path)
        assert link == sharing_service.create_link.return_value


class TestGetLink:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        sharing_service = cast(mock.MagicMock, sharing_use_case.sharing)
        # WHEN
        link = await sharing_use_case.get_link(ns_path, path)
        # THEN
        file_service.get_at_path.assert_awaited_once_with(ns_path, path)
        assert link == sharing_service.get_link_by_file_id.return_value


class TestGetLinkThumbnail:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        token = "shared-link-token"
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        sharing_service = cast(mock.MagicMock, sharing_use_case.sharing)
        # WHEN
        result = await sharing_use_case.get_link_thumbnail(token, size=32)
        # THEN
        sharing_service.get_link_by_token.assert_awaited_once_with(token)
        file_service.thumbnail.assert_awaited_once_with(
            sharing_service.get_link_by_token.return_value.file_id, size=32
        )
        assert result == file_service.thumbnail.return_value


class TestGetSharedItem:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        token = "shared-link-token"
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        sharing_service = cast(mock.MagicMock, sharing_use_case.sharing)
        # WHEN
        file = await sharing_use_case.get_shared_item(token)
        # THEN
        sharing_service.get_link_by_token.assert_awaited_once_with(token)
        file_service.filecore.get_by_id.assert_awaited_once_with(
            sharing_service.get_link_by_token.return_value.file_id,
        )
        assert file == file_service.filecore.get_by_id.return_value


class TestListMember:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        ns_path, file_id = "admin", uuid.uuid4()
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        file_member_service = cast(mock.MagicMock, sharing_use_case.file_member)
        ns_service = cast(mock.MagicMock, sharing_use_case.namespace)
        # WHEN
        result = await sharing_use_case.list_members(ns_path, file_id)
        # THEN
        assert result == file_member_service.list_all.return_value
        file_service.get_by_id.assert_awaited_once_with(ns_path, file_id)
        file = file_service.get_by_id.return_value
        file_member_service.list_all.assert_awaited_once_with(file.id)
        ns_service.get_by_path.assert_not_awaited()
        file_member_service.get.assert_not_awaited()

    async def test_listing_by_a_member_that_can_not_view_a_file(
        self, sharing_use_case: SharingUseCase
    ):
        # GIVEN
        user_id = uuid.uuid4()
        source_file = _make_folder("admin", "f.txt")
        file = _make_mounted_file(source_file, "user", "f.txt")
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        file_service.get_by_id.side_effect = File.ActionNotAllowed
        file_member_service = cast(mock.MagicMock, sharing_use_case.file_member)
        ns_service = cast(mock.MagicMock, sharing_use_case.namespace)
        ns_service.get_by_path.return_value = Namespace(
            id=uuid.uuid4(),
            path="user",
            owner_id=user_id,
        )

        # WHEN
        result = await sharing_use_case.list_members(file.ns_path, file.id)

        # THEN
        file_service.get_by_id.assert_awaited_once_with(file.ns_path, file.id)
        file_member_service.list_all.assert_not_awaited()

        ns_service.get_by_path.assert_awaited_once_with(file.ns_path)
        ns = ns_service.get_by_path.return_value
        file_member_service.get.assert_awaited_once_with(file.id, ns.owner_id)
        members = file_member_service.get.return_value
        assert result == [members]

    async def test_when_listing_by_not_a_member(
        self, sharing_use_case: SharingUseCase
    ):
        # GIVEN
        user_id = uuid.uuid4()
        source_file = _make_folder("admin", "f.txt")
        file = _make_mounted_file(source_file, "user", "f.txt")
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        file_service.get_by_id.side_effect = File.ActionNotAllowed
        ns_service = cast(mock.MagicMock, sharing_use_case.namespace)
        ns_service.get_by_path.return_value = Namespace(
            id=uuid.uuid4(),
            path="user",
            owner_id=user_id,
        )
        file_member_service = cast(mock.MagicMock, sharing_use_case.file_member)
        file_member_service.get.side_effect = FileMember.NotFound
        # WHEN
        with pytest.raises(File.ActionNotAllowed):
            await sharing_use_case.list_members(file.ns_path, file.id)
        # THEN
        file_service.get_by_id.assert_awaited_once_with(file.ns_path, file.id)
        file_member_service.list_all.assert_not_awaited()

        ns_service.get_by_path.assert_awaited_once_with(file.ns_path)
        ns = ns_service.get_by_path.return_value
        file_member_service.get.assert_awaited_once_with(file.id, ns.owner_id)



class TestRemoveFileMember:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        file, user_id = _make_file("admin", "f.txt"), uuid.uuid4()
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        file_service.get_by_id.return_value = file
        file_member_service = cast(mock.MagicMock, sharing_use_case.file_member)
        ns_service = cast(mock.MagicMock, sharing_use_case.namespace)
        # WHEN
        await sharing_use_case.remove_member(file.ns_path, file.id, user_id)
        # THEN
        file_service.get_by_id.assert_awaited_once_with(file.ns_path, file.id)
        ns_service.get_by_path.assert_awaited_once_with(file.ns_path)
        file_member_service.remove.assert_awaited_once_with(file.id, user_id)

    async def test_member_can_always_remove_itself(
        self, sharing_use_case: SharingUseCase
    ):
        # GIVEN
        user_id = uuid.uuid4()
        source_file = _make_folder("admin", "f.txt")
        file = _make_mounted_file(source_file, "user", "f.txt")
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        file_service.get_by_id.return_value = file
        file_member_service = cast(mock.MagicMock, sharing_use_case.file_member)
        ns_service = cast(mock.MagicMock, sharing_use_case.namespace)
        ns_service.get_by_path.return_value = Namespace(
            id=uuid.uuid4(),
            path="user",
            owner_id=user_id,
        )
        # WHEN
        await sharing_use_case.remove_member(file.ns_path, file.id, user_id)
        # THEN
        file_service.get_by_id.assert_awaited_once_with(file.ns_path, file.id)
        ns_service.get_by_path.assert_awaited_once_with(file.ns_path)
        file_member_service.remove.assert_awaited_once_with(file.id, user_id)

    async def test_when_not_allowed(self, sharing_use_case: SharingUseCase):
        # GIVEN
        user_id = uuid.uuid4()
        source_file = _make_folder("admin", "f.txt")
        file = _make_mounted_file(source_file, "user", "f.txt")
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        file_service.get_by_id.return_value = file
        file_member_service = cast(mock.MagicMock, sharing_use_case.file_member)
        ns_service = cast(mock.MagicMock, sharing_use_case.namespace)
        # WHEN
        with pytest.raises(File.ActionNotAllowed):
            await sharing_use_case.remove_member(file.ns_path, file.id, user_id)
        # THEN
        file_service.get_by_id.assert_awaited_once_with(file.ns_path, file.id)
        ns_service.get_by_path.assert_awaited_once_with(file.ns_path)
        file_member_service.remove.assert_not_awaited()


class TestRevokeLink:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        token = "shared-link-token"
        sharing_service = cast(mock.MagicMock, sharing_use_case.sharing)
        # WHEN
        await sharing_use_case.revoke_link(token)
        # THEN
        sharing_service.revoke_link.assert_awaited_once_with(token)


class TestSetMemberActions:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        file, user_id = _make_file("admin", "f.txt"), uuid.uuid4()
        actions = FileMember.VIEWER
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        file_service.get_by_id.return_value = file
        file_member_service = cast(mock.MagicMock, sharing_use_case.file_member)
        # WHEN
        await sharing_use_case.set_member_actions(
            file.ns_path, file.id, user_id, actions=actions
        )
        # THEN
        file_service.get_by_id.assert_awaited_once_with(file.ns_path, file.id)
        file_member_service.set_actions.assert_awaited_once_with(
            file.id, user_id, actions=actions
        )

    async def test_when_not_allowed(self, sharing_use_case: SharingUseCase):
        # GIVEN
        user_id, actions = uuid.uuid4(), FileMember.EDITOR
        source_file = _make_folder("admin", "f.txt")
        file = _make_mounted_file(source_file, "user", "f.txt")
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        file_service.get_by_id.return_value = file
        file_member_service = cast(mock.MagicMock, sharing_use_case.file_member)
        # WHEN
        with pytest.raises(File.ActionNotAllowed):
            await sharing_use_case.set_member_actions(
                file.ns_path, file.id, user_id, actions=actions
            )
        # THEN
        file_service.get_by_id.assert_awaited_once_with(file.ns_path, file.id)
        file_member_service.set_actions.assert_not_awaited()
