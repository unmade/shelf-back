from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

if TYPE_CHECKING:
    from app.app.photos.services import MediaItemService

pytestmark = [pytest.mark.anyio]


class TestListForUser:
    async def test(self, media_item_service: MediaItemService):
        # GIVEN
        user_id = uuid.uuid4()
        db = cast(mock.AsyncMock, media_item_service.db)
        # WHEN
        result = await media_item_service.list_for_user(user_id, offset=100, limit=50)
        # THEN
        assert result == db.media_item.list_by_user_id.return_value
        db.media_item.list_by_user_id.assert_awaited_once_with(
            user_id, offset=100, limit=50
        )
