from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.domain.entities import SENTINEL_ID, SharedLink

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.services import SharingService

pytestmark = [pytest.mark.asyncio]


@mock.patch("secrets.token_urlsafe")
class TestGetOrCreate:
    async def test(self, token_mock: MagicMock, sharing_service: SharingService):
        # GIVEN
        file_id = str(uuid.uuid4())
        token_mock.return_value = "ec67376f"
        # WHEN
        link = await sharing_service.get_or_create_shared_link(file_id)
        # THEN
        db = cast(mock.MagicMock, sharing_service.db)
        db.shared_link.save.assert_awaited_once_with(
            SharedLink(
                id=SENTINEL_ID,
                file_id=file_id,
                token=token_mock.return_value,
            )
        )
        assert link == db.shared_link.save.return_value


class TestRevokeSharedLink:
    async def test(self, sharing_service: SharingService):
        token = "ec67376f"
        await sharing_service.revoke_shared_link(token)
        db = cast(mock.MagicMock, sharing_service.db)
        db.shared_link.delete.assert_awaited_once_with(token)
