from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.files.domain import SharedLink
from app.app.infrastructure.database import SENTINEL_ID

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.files.services import SharingService

pytestmark = [pytest.mark.asyncio]


@mock.patch("secrets.token_urlsafe")
class TestCreateLink:
    async def test(self, token_mock: MagicMock, sharing_service: SharingService):
        # GIVEN
        file_id = uuid.uuid4()
        token_mock.return_value = "ec67376f"
        # WHEN
        link = await sharing_service.create_link(file_id)
        # THEN
        db = cast(mock.MagicMock, sharing_service.db)
        db.shared_link.save.assert_awaited_once_with(
            SharedLink.model_construct(
                id=SENTINEL_ID,
                file_id=file_id,
                token=token_mock.return_value,
                created_at=mock.ANY,
            )
        )
        assert link == db.shared_link.save.return_value


class TestGetLinkByFileID:
    async def test(self, sharing_service: SharingService):
        # GIVEN
        file_id = uuid.uuid4()
        # WHEN
        link = await sharing_service.get_link_by_file_id(file_id)
        # THEN
        db = cast(mock.MagicMock, sharing_service.db)
        db.shared_link.get_by_file_id.assert_awaited_once_with(file_id)
        assert link == db.shared_link.get_by_file_id.return_value


class TestGetLinkByToken:
    async def test(self, sharing_service: SharingService):
        # GIVEN
        token = str(uuid.uuid4())
        # WHEN
        link = await sharing_service.get_link_by_token(token)
        # THEN
        db = cast(mock.MagicMock, sharing_service.db)
        db.shared_link.get_by_token.assert_awaited_once_with(token)
        assert link == db.shared_link.get_by_token.return_value


class TestListLinksByNS:
    async def test(self, sharing_service: SharingService):
        # GIVEN
        ns_path = "admin"
        # WHEN
        result = await sharing_service.list_links_by_ns(ns_path, offset=25, limit=10)
        # THEN
        db = cast(mock.MagicMock, sharing_service.db)
        db.shared_link.list_by_ns.assert_awaited_once_with(ns_path, offset=25, limit=10)
        assert result == db.shared_link.list_by_ns.return_value


class TestRevokeLink:
    async def test(self, sharing_service: SharingService):
        token = "ec67376f"
        await sharing_service.revoke_link(token)
        db = cast(mock.MagicMock, sharing_service.db)
        db.shared_link.delete.assert_awaited_once_with(token)
