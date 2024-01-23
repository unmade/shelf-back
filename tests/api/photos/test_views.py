from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.api.photos.exceptions import MediaItemNotFound
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


class TestListMediaItemCategories:
    url = "/photos/list_media_item_categories"

    async def test(
        self, client: TestClient, photos_use_case: MagicMock, user: User,
    ):
        # GIVEN
        file_id = uuid.uuid4()
        photos_use_case.list_media_item_categories.return_value = [
            MediaItem.Category(
                name=MediaItem.Category.Name.ANIMALS,
                origin=MediaItem.Category.Origin.AUTO,
                probability=54,
            ),
            MediaItem.Category(
                name=MediaItem.Category.Name.PETS,
                origin=MediaItem.Category.Origin.AUTO,
                probability=62,
            ),
        ]
        payload = {"file_id": str(file_id)}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.status_code == 200
        photos_use_case.list_media_item_categories.assert_awaited_once_with(
            user.id, file_id
        )

    async def test_when_media_item_not_found(
        self,
        client: TestClient,
        photos_use_case: MagicMock,
        user: User,
    ):
        # GIVEN
        file_id = uuid.uuid4()
        photos_use_case.list_media_item_categories.side_effect = MediaItem.NotFound
        payload = {"file_id": str(file_id)}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.status_code == 404
        photos_use_case.list_media_item_categories.assert_awaited_once_with(
            user.id, file_id
        )


class TestSetCategories:
    url = "/photos/set_media_item_categories"

    async def test(self, client: TestClient, photos_use_case: MagicMock, user: User):
        # GIVEN
        file_id = uuid.uuid4()
        categories = [
            MediaItem.Category.Name.ANIMALS,
            MediaItem.Category.Name.PETS,
        ]
        payload = {
            "file_id": str(file_id),
            "categories": categories,
        }
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        photos_use_case.set_media_item_categories.assert_awaited_once_with(
            user.id, file_id, categories=categories
        )
        assert response.status_code == 200

    async def test_when_media_item_not_found(
        self,
        client: TestClient,
        photos_use_case: MagicMock,
        user: User,
    ):
        # GIVEN
        file_id = uuid.uuid4()
        payload = {
            "file_id": str(file_id),
            "categories": [],
        }
        photos_use_case.set_media_item_categories.side_effect = MediaItem.NotFound
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        photos_use_case.set_media_item_categories.assert_awaited_once_with(
            user.id, file_id, categories=[]
        )
        assert response.status_code == 404
        assert response.json() == MediaItemNotFound().as_dict()
