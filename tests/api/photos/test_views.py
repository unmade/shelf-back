from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.api.photos.exceptions import MediaItemNotFound
from app.app.files.domain import SharedLink
from app.app.photos.domain import MediaItem
from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from unittest.mock import MagicMock
    from uuid import UUID

    from app.app.users.domain import User
    from tests.api.conftest import TestClient

pytestmark = [pytest.mark.anyio]


def _make_media_item(
    name: str | None = None, mediatype: str | None = None
) -> MediaItem:
    return MediaItem(
        file_id=uuid.uuid4(),
        name=name or f"{uuid.uuid4().hex}.jpeg",
        size=12,
        mediatype=mediatype or MediaType.IMAGE_JPEG,  # type: ignore
    )

def _make_shared_link(file_id: UUID) -> SharedLink:
    return SharedLink(
        id=uuid.uuid4(),
        file_id=file_id,
        token=uuid.uuid4().hex,
    )


class TestDeleteMediaItemBatch:
    url = "/photos/delete_media_item_batch"

    async def test(
        self, client: TestClient, photos_use_case: MagicMock, user: User,
    ):
        # GIVEN
        items = [
            _make_media_item("img.jpeg", mediatype="image/jpeg"),
            _make_media_item("img.png", mediatype="image/png"),
        ]
        file_ids = [item.file_id for item in items]
        photos_use_case.delete_media_item_batch.return_value = items
        payload = {"file_ids": [str(file_id) for file_id in file_ids]}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        photos_use_case.delete_media_item_batch.assert_awaited_once_with(
            user.id, file_ids
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(items)
        assert response.json()["items"][0]["name"] == "img.jpeg"
        assert response.json()["items"][0]["thumbnail_url"] is not None
        assert response.json()["items"][1]["name"] == "img.png"
        assert response.json()["items"][1]["thumbnail_url"] is not None


class TestEmptyTrash:
    url = "/photos/empty_trash"

    async def test(
        self, client: TestClient, photos_use_case: MagicMock, user: User,
    ):
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url)
        # THEN
        photos_use_case.empty_trash.assert_awaited_once_with(user.id)
        assert response.status_code == 200


class TestDeleteMediaItemImmediatelyBatch:
    url = "/photos/delete_media_item_immediately_batch"

    async def test(
        self, client: TestClient, photos_use_case: MagicMock, user: User,
    ):
        # GIVEN
        file_ids = [uuid.uuid4(), uuid.uuid4()]
        payload = {"file_ids": [str(file_id) for file_id in file_ids]}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        photos_use_case.delete_media_item_immediately_batch.assert_awaited_once_with(
            user.id, file_ids
        )
        assert response.status_code == 200


class TestListDeletedMediaItems:
    url = "/photos/list_deleted_media_items"

    async def test(
        self, client: TestClient, photos_use_case: MagicMock, user: User,
    ):
        # GIVEN
        items = [
            _make_media_item("img.jpeg", mediatype="image/jpeg"),
            _make_media_item("img.png", mediatype="image/png"),
        ]
        photos_use_case.list_deleted_media_items.return_value = items
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        photos_use_case.list_deleted_media_items.assert_awaited_once_with(user.id)
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(items)
        assert response.json()["items"][0]["name"] == "img.jpeg"
        assert response.json()["items"][0]["thumbnail_url"] is not None
        assert response.json()["items"][1]["name"] == "img.png"
        assert response.json()["items"][1]["thumbnail_url"] is not None


class TestListMediaItems:
    url = "/photos/list_media_items"

    async def test(
        self, client: TestClient, photos_use_case: MagicMock, user: User,
    ):
        # GIVEN
        items = [
            _make_media_item("img.jpeg", mediatype="image/jpeg"),
            _make_media_item("img.svg", mediatype="image/svg+xml"),
        ]
        photos_use_case.list_media_items.return_value = items
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        photos_use_case.list_media_items.assert_awaited_once_with(
            user.id, only_favourites=False, offset=0, limit=1000
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(items)
        assert response.json()["items"][0]["name"] == "img.jpeg"
        assert response.json()["items"][0]["thumbnail_url"] is not None
        assert response.json()["items"][1]["name"] == "img.svg"
        assert response.json()["items"][1]["thumbnail_url"] is None


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


class TestListSharedLinks:
    url = "/photos/list_shared_links"

    async def test(self, client: TestClient, photos_use_case: MagicMock, user: User):
        # GIVEN
        media_items = [_make_media_item() for _ in range(3)]
        links = [_make_shared_link(item.file_id) for item in media_items]
        photos_use_case.list_shared_links.return_value = list(
            zip(media_items, links, strict=False)
        )
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        assert response.status_code == 200
        assert len(response.json()["items"]) == 3


class TestRestoreMediaItemBatch:
    url = "/photos/restore_media_item_batch"

    async def test(
        self, client: TestClient, photos_use_case: MagicMock, user: User,
    ):
        # GIVEN
        items = [
            _make_media_item("img.jpeg", mediatype="image/jpeg"),
            _make_media_item("img.png", mediatype="image/png"),
        ]
        file_ids = [item.file_id for item in items]
        photos_use_case.restore_media_item_batch.return_value = items
        payload = {"file_ids": [str(file_id) for file_id in file_ids]}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        photos_use_case.restore_media_item_batch.assert_awaited_once_with(
            user.id, file_ids
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(items)
        assert response.json()["items"][0]["name"] == "img.jpeg"
        assert response.json()["items"][0]["thumbnail_url"] is not None
        assert response.json()["items"][1]["name"] == "img.png"
        assert response.json()["items"][1]["thumbnail_url"] is not None


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
