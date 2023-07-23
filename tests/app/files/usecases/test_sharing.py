from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.files.domain import FileMember

if TYPE_CHECKING:
    from app.app.files.usecases import SharingUseCase

pytestmark = [pytest.mark.asyncio]


class TestAddMember:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        ns_path, file_id, username = "admin", str(uuid.uuid4()), "user"
        user_service = cast(mock.MagicMock, sharing_use_case.user)
        file_service = cast(mock.MagicMock, sharing_use_case.file)
        file_member_service = cast(mock.MagicMock, sharing_use_case.file_member)
        # WHEN
        member = await sharing_use_case.add_member(ns_path, file_id, username)
        # THEN
        assert member == file_member_service.add.return_value
        user_service.get_by_username.assert_awaited_once_with(username)
        user = user_service.get_by_username.return_value
        file_member_service.add.assert_awaited_once_with(
            file_id, user.id, actions=FileMember.EDITOR
        )
        file_service.mount.assert_awaited_once_with(
            file_id, at_folder=(user.username, ".")
        )


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
        ns_path, file_id = "admin", str(uuid.uuid4())
        file_member_service = cast(mock.MagicMock, sharing_use_case.file_member)
        # WHEN
        members = await sharing_use_case.list_members(ns_path, file_id)
        # THEN
        assert members == file_member_service.list_all.return_value
        file_member_service.list_all.assert_awaited_once_with(file_id)


class TestRemoveFileMember:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        file_id, user_id = str(uuid.uuid4()), uuid.uuid4()
        file_member_service = cast(mock.MagicMock, sharing_use_case.file_member)
        # WHEN
        await sharing_use_case.remove_member(file_id, user_id)
        # THEN
        file_member_service.remove.assert_awaited_once_with(file_id, user_id)


class TestRevokeLink:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        token = "shared-link-token"
        sharing_service = cast(mock.MagicMock, sharing_use_case.sharing)
        # WHEN
        await sharing_use_case.revoke_link(token)
        # THEN
        sharing_service.revoke_link.assert_awaited_once_with(token)
