from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.photos.domain import MediaItem

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.users.domain import User
    from tests.api.conftest import TestClient

pytestmark = [pytest.mark.anyio]

def _make_media_item(name: str, mediatype: str) -> MediaItem:
    return MediaItem(
        file_id=uuid.uuid4(),
        name=name,
        size=12,
        mediatype=mediatype,  # type: ignore
    )


class TestListMediaItems:
    url = "/photos/list_media_items"

    async def test(
        self, client: TestClient, photos_use_case: MagicMock, user: User,
    ):
        # GIVEN
        items = [
            _make_media_item("img.jpeg", mediatype="image/jpeg"),
            _make_media_item("img.png", mediatype="image/png"),
        ]
        photos_use_case.list_media_items.return_value = items
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        photos_use_case.list_media_items.assert_awaited_once_with(
            user.id, offset=0, limit=1000
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(items)
        assert response.json()["items"][0]["name"] == "img.jpeg"
        assert response.json()["items"][0]["thumbnail_url"] is not None
        assert response.json()["items"][1]["name"] == "img.png"
        assert response.json()["items"][1]["thumbnail_url"] is not None
