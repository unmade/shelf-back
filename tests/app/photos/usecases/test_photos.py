from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

if TYPE_CHECKING:
    from app.app.photos.usecases import PhotosUseCase

pytestmark = [pytest.mark.anyio]


class TestListMediaItems:
    async def test(self, photos_use_case: PhotosUseCase):
        # GIVEN
        user_id = uuid.uuid4()
        media_item_service = cast(mock.MagicMock, photos_use_case.media_item)
        # WHEN
        result = await photos_use_case.list_media_items(user_id, offset=0, limit=25)
        # THEN
        assert result == media_item_service.list_for_user.return_value
        media_item_service.list_for_user.assert_awaited_once_with(
            user_id, offset=0, limit=25
        )