from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

if TYPE_CHECKING:
    from app.app.files.usecases import SharingUseCase

pytestmark = [pytest.mark.asyncio]


class TestCreateLink:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        filecore = cast(mock.MagicMock, sharing_use_case.filecore)
        sharing_service = cast(mock.MagicMock, sharing_use_case.sharing)
        # WHEN
        link = await sharing_use_case.create_link(ns_path, path)
        # THEN
        filecore.get_by_path.assert_awaited_once_with(ns_path, path)
        assert link == sharing_service.create_link.return_value


class TestGetLink:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        ns_path, path = "admin", "f.txt"
        filecore = cast(mock.MagicMock, sharing_use_case.filecore)
        sharing_service = cast(mock.MagicMock, sharing_use_case.sharing)
        # WHEN
        link = await sharing_use_case.get_link(ns_path, path)
        # THEN
        filecore.get_by_path.assert_awaited_once_with(ns_path, path)
        assert link == sharing_service.get_link_by_file_id.return_value


class TestGetLinkThumbnail:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        token = "shared-link-token"
        file_service = cast(mock.MagicMock, sharing_use_case.file_service)
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
        filecore = cast(mock.MagicMock, sharing_use_case.filecore)
        sharing_service = cast(mock.MagicMock, sharing_use_case.sharing)
        # WHEN
        file = await sharing_use_case.get_shared_item(token)
        # THEN
        sharing_service.get_link_by_token.assert_awaited_once_with(token)
        filecore.get_by_id.assert_awaited_once_with(
            sharing_service.get_link_by_token.return_value.file_id,
        )
        assert file == filecore.get_by_id.return_value


class TestRevokeLink:
    async def test(self, sharing_use_case: SharingUseCase):
        # GIVEN
        token = "shared-link-token"
        sharing_service = cast(mock.MagicMock, sharing_use_case.sharing)
        # WHEN
        await sharing_use_case.revoke_link(token)
        # THEN
        sharing_service.revoke_link.assert_awaited_once_with(token)
