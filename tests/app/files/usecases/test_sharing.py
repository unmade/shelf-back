from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.files.domain import File
from app.config import config

if TYPE_CHECKING:
    from app.app.files.usecases import SharingUseCase

pytestmark = [pytest.mark.anyio]


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
        assert result == (file, *thumbnail)
        sharing_service.get_link_by_token.assert_awaited_once_with(token)
        file_service.filecore.get_by_id.assert_awaited_once_with(link.file_id)
        thumbnailer.thumbnail.assert_awaited_once_with(file.blob_id, file.chash, 32)


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


class TestRevokeLink:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        token = "shared-link-token"
        sharing_service = cast(mock.MagicMock, sharing_use_case.sharing)
        # WHEN
        await sharing_use_case.revoke_link(token)
        # THEN
        sharing_service.revoke_link.assert_awaited_once_with(token)
