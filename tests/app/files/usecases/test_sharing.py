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
from app.config import config
from app.toolkit import chash

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath
    from app.app.files.usecases import SharingUseCase

pytestmark = [pytest.mark.anyio]


def _make_file(
    ns_path: str, path: AnyPath, size: int = 10, mediatype: str = "plain/text"
) -> File:
    path = Path(path)
    return File(
        id=uuid.uuid4(),
        ns_path=ns_path,
        name=path.name,
        path=path,
        chash=chash.EMPTY_CONTENT_HASH,
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
            chash=source_file.chash,
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
                actions=MountPoint.Actions(),
            ),
        )


class TestAddMember:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        file, username = _make_file("admin", "f.txt"), "user"
        user_service = cast(mock.MagicMock, sharing_use_case.user)
        ns_service = cast(mock.MagicMock, sharing_use_case.namespace)
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        file_service.get_by_id.return_value = file
        file_member_service = cast(mock.MagicMock, sharing_use_case.file_member)
        # WHEN
        member = await sharing_use_case.add_member(file.ns_path, file.id, username)
        # THEN: both owner and a member are added
        assert member == file_member_service.add.return_value
        file_service.get_by_id.assert_awaited_once_with(file.ns_path, file.id)
        user_service.get_by_username.assert_awaited_once_with(username)
        user = user_service.get_by_username.return_value
        ns_service.get_by_path.assert_awaited_once_with(file.ns_path)
        namespace = ns_service.get_by_path.return_value
        file_member_service.add.assert_has_awaits([
            mock.call(file.id, namespace.owner_id, actions=FileMember.OWNER),
            mock.call(file.id, user.id, actions=FileMember.EDITOR),
        ])
        file_service.mount.assert_awaited_once_with(
            file.id, at_folder=(user.username, ".")
        )

    async def test_is_not_added(self, sharing_use_case: SharingUseCase):
        # GIVEN
        file, username = _make_file("admin", "f.txt"), "user"
        user_service = cast(mock.MagicMock, sharing_use_case.user)
        ns_service = cast(mock.MagicMock, sharing_use_case.namespace)
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        file_service.get_by_id.return_value = file
        file_member_service = cast(mock.MagicMock, sharing_use_case.file_member)
        # WHEN
        member = await sharing_use_case.add_member("user", file.id, username)
        # THEN: both owner and a member are added
        assert member == file_member_service.add.return_value
        file_service.get_by_id.assert_awaited_once_with("user", file.id)
        user_service.get_by_username.assert_awaited_once_with(username)
        user = user_service.get_by_username.return_value
        ns_service.get_by_path.assert_not_awaited()
        file_member_service.add.assert_awaited_once_with(
            file.id, user.id, actions=FileMember.EDITOR,
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
        ns_path, file_id = "admin", uuid.uuid4()
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        sharing_service = cast(mock.MagicMock, sharing_use_case.sharing)
        user_service = cast(mock.MagicMock, sharing_use_case.user)
        # WHEN
        with mock.patch.object(config.features, "shared_links_enabled", True):
            link = await sharing_use_case.create_link(ns_path, file_id)
        # THEN
        assert link == sharing_service.create_link.return_value
        file_service.get_by_id.assert_awaited_once_with(ns_path, file_id)
        file = file_service.get_by_id.return_value
        sharing_service.create_link.assert_awaited_once_with(file.id)
        user_service.get_by_username.assert_not_awaited()

    async def test_always_enabled_for_superuser(self, sharing_use_case: SharingUseCase):
        # GIVEN
        ns_path, file_id = "admin", uuid.uuid4()
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        sharing_service = cast(mock.MagicMock, sharing_use_case.sharing)
        user_service = cast(mock.MagicMock, sharing_use_case.user)
        user = user_service.get_by_username.return_value
        user.superuser = True
        # WHEN
        with (
            mock.patch.object(config.features, "shared_links_enabled", False),
        ):
            link = await sharing_use_case.create_link(ns_path, file_id)
        # THEN
        assert link == sharing_service.create_link.return_value
        file_service.get_by_id.assert_awaited_once_with(ns_path, file_id)
        file = file_service.get_by_id.return_value
        sharing_service.create_link.assert_awaited_once_with(file.id)
        user_service.get_by_username.assert_awaited_once_with(ns_path)

    async def test_when_disabled(self, sharing_use_case: SharingUseCase):
        # GIVEN
        ns_path, file_id = "admin", uuid.uuid4()
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        sharing_service = cast(mock.MagicMock, sharing_use_case.sharing)
        user_service = cast(mock.MagicMock, sharing_use_case.user)
        user = user_service.get_by_username.return_value
        user.superuser = False
        # WHEN
        with (
            mock.patch.object(config.features, "shared_links_enabled", False),
            pytest.raises(File.ActionNotAllowed),
        ):
            await sharing_use_case.create_link(ns_path, file_id)
        # THEN
        file_service.get_by_id.assert_not_awaited()
        sharing_service.create_link.assert_not_awaited()
        user_service.get_by_username.assert_awaited_once_with(ns_path)


class TestGetLink:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        ns_path, file_id = "admin", uuid.uuid4()
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        sharing_service = cast(mock.MagicMock, sharing_use_case.sharing)
        # WHEN
        link = await sharing_use_case.get_link(ns_path, file_id)
        # THEN
        file_service.get_by_id.assert_awaited_once_with(ns_path, file_id)
        assert link == sharing_service.get_link_by_file_id.return_value


class TestGetLinkThumbnail:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        token = "shared-link-token"
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        file = file_service.filecore.get_by_id.return_value
        sharing_service = cast(mock.MagicMock, sharing_use_case.sharing)
        link = sharing_service.get_link_by_token.return_value
        thumbnailer = cast(mock.MagicMock, sharing_use_case.thumbnailer)
        thumbnail = thumbnailer.thumbnail.return_value
        # WHEN
        result = await sharing_use_case.get_link_thumbnail(token, size=32)
        # THEN
        assert result == (file, thumbnail)
        sharing_service.get_link_by_token.assert_awaited_once_with(token)
        file_service.filecore.get_by_id.assert_awaited_once_with(link.file_id)
        thumbnailer.thumbnail.assert_awaited_once_with(file.id, file.chash, 32)


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


class TestListMemberBatch:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        ns_path, file_ids = "admin", [uuid.uuid4(), uuid.uuid4()]
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        file_member_service = cast(mock.MagicMock, sharing_use_case.file_member)
        # WHEN
        result = await sharing_use_case.list_members_batch(ns_path, file_ids)
        # THEN
        assert result == file_member_service.list_by_file_id_batch.return_value
        file_service.get_by_id_batch.assert_awaited_once_with(ns_path, ids=file_ids)
        files = file_service.get_by_id_batch.return_value
        file_member_service.list_by_file_id_batch.assert_awaited_once_with(
            [file.id for file in files]
        )


class TestListSharedFiles:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        ns_path, user_id = "admin", uuid.uuid4()
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        file_member_service = cast(mock.MagicMock, sharing_use_case.file_member)
        # WHEN
        result = await sharing_use_case.list_shared_files(ns_path, user_id)
        # THEN
        assert result == file_service.get_by_id_batch.return_value
        file_member_service.list_by_user_id.assert_awaited_once_with(user_id, limit=50)
        members = file_member_service.list_by_user_id.return_value
        ids = [item.file_id for item in members]
        file_service.get_by_id_batch.assert_awaited_once_with(ns_path, ids=ids)


class TestListSharedLinks:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        ns_path = "admin"
        sharing = cast(mock.MagicMock, sharing_use_case.sharing)
        # WHEN
        result = await sharing_use_case.list_shared_links(ns_path)
        # THEN
        assert result == sharing.list_links_by_ns.return_value
        sharing.list_links_by_ns.assert_awaited_once_with(ns_path, limit=50)


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
