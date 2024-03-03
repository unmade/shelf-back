from __future__ import annotations

import urllib.parse
import uuid
from io import BytesIO
from typing import TYPE_CHECKING

import pytest

from app.api.photos.exceptions import DownloadNotFound, MediaItemNotFound
from app.app.files.domain import SharedLink
from app.app.photos.domain import MediaItem
from app.app.photos.repositories.media_item import CountResult
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


class TestCount:
    url = "/photos/media_items/count"

    async def test(
        self, client: TestClient, photos_use_case: MagicMock, user: User,
    ):
        # GIVEN
        count_result = CountResult(total=4, deleted=2)
        photos_use_case.count.return_value = count_result
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        photos_use_case.count.assert_awaited_once_with(user.id)
        assert response.json() == {
            "total": count_result.total,
            "deleted": count_result.deleted,
        }
        assert response.status_code == 200


class TestDeletedBatch:
    url = "/photos/media_items/delete_batch"

    async def test(
        self, client: TestClient, photos_use_case: MagicMock, user: User,
    ):
        # GIVEN
        items = [
            _make_media_item("img.jpeg", mediatype="image/jpeg"),
            _make_media_item("img.png", mediatype="image/png"),
        ]
        file_ids = [item.file_id for item in items]
        photos_use_case.delete_batch.return_value = items
        payload = {"file_ids": [str(file_id) for file_id in file_ids]}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        photos_use_case.delete_batch.assert_awaited_once_with(
            user.id, file_ids
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(items)
        assert response.json()["items"][0]["name"] == "img.jpeg"
        assert response.json()["items"][0]["thumbnail_url"] is not None
        assert response.json()["items"][1]["name"] == "img.png"
        assert response.json()["items"][1]["thumbnail_url"] is not None


class TestDeletedImmediatelyBatch:
    url = "/photos/media_items/delete_immediately_batch"

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
        photos_use_case.delete_immediately_batch.assert_awaited_once_with(
            user.id, file_ids
        )
        assert response.status_code == 200


class TestDownloadBatch:
    def url(self, key: str) -> str:
        return f"/photos/media_items/download_batch?key={key}"

    async def test(
        self, client: TestClient, photos_use_case: MagicMock, user: User,
    ):
        # GIVEN
        key = uuid.uuid4().hex
        photos_use_case.download_batch.return_value = BytesIO(b"I'm a ZIP archive")
        session = photos_use_case.download_batch_get_session.return_value
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url(key))
        # THEN
        assert response.status_code == 200
        content_disposition_value = 'attachment; filename="Shelf Cloud.zip"'
        assert response.headers["Content-Disposition"] == content_disposition_value
        assert "Content-Length" not in response.headers
        assert response.content == b"I'm a ZIP archive"
        photos_use_case.download_batch.assert_called_once_with(session)

    async def test_when_key_is_invalid(
        self,
        client: TestClient,
        photos_use_case: MagicMock,
        user: User,
    ):
        # GIVEN
        key = uuid.uuid4().hex
        photos_use_case.download_batch_get_session.return_value = None
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url(key))
        # THEN
        assert response.status_code == 404
        assert response.json() == DownloadNotFound().as_dict()
        photos_use_case.download_batch_get_session.assert_awaited_once_with(key)


class TestGetDownloadURL:
    url = "/photos/media_items/get_download_url"

    async def test(
        self, client: TestClient, photos_use_case: MagicMock, user: User,
    ):
        # GIVEN
        key = uuid.uuid4().hex
        photos_use_case.download_batch_create_session.return_value = key
        file_ids = [uuid.uuid4() for _ in range(3)]
        payload = {"file_ids": [str(file_id) for file_id in file_ids]}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.status_code == 200
        download_url = response.json()["download_url"]
        assert download_url.startswith(str(client.base_url))
        assert "/download_batch?" in download_url
        assert response.status_code == 200
        parts = urllib.parse.urlsplit(download_url)
        qs = urllib.parse.parse_qs(parts.query)
        assert len(qs["key"]) == 1
        photos_use_case.download_batch_create_session.assert_called_once_with(
            user.id, file_ids
        )


class TestList:
    url = "/photos/media_items/list"

    async def test(
        self, client: TestClient, photos_use_case: MagicMock, user: User,
    ):
        # GIVEN
        items = [
            _make_media_item("img.jpeg", mediatype="image/jpeg"),
            _make_media_item("img.svg", mediatype="image/svg+xml"),
        ]
        photos_use_case.list_.return_value = items
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        photos_use_case.list_.assert_awaited_once_with(
            user.id, only_favourites=False, offset=0, limit=100
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(items)
        assert response.json()["items"][0]["name"] == "img.jpeg"
        assert response.json()["items"][0]["thumbnail_url"] is not None
        assert response.json()["items"][1]["name"] == "img.svg"
        assert response.json()["items"][1]["thumbnail_url"] is None


class TestListDeleted:
    url = "/photos/media_items/list_deleted"

    async def test(
        self, client: TestClient, photos_use_case: MagicMock, user: User,
    ):
        # GIVEN
        items = [
            _make_media_item("img.jpeg", mediatype="image/jpeg"),
            _make_media_item("img.png", mediatype="image/png"),
        ]
        photos_use_case.list_deleted.return_value = items
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        photos_use_case.list_deleted.assert_awaited_once_with(user.id)
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(items)
        assert response.json()["items"][0]["name"] == "img.jpeg"
        assert response.json()["items"][0]["thumbnail_url"] is not None
        assert response.json()["items"][1]["name"] == "img.png"
        assert response.json()["items"][1]["thumbnail_url"] is not None


class TestListCategories:
    url = "/photos/media_items/list_categories"

    async def test(
        self, client: TestClient, photos_use_case: MagicMock, user: User,
    ):
        # GIVEN
        file_id = uuid.uuid4()
        photos_use_case.list_categories.return_value = [
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
        photos_use_case.list_categories.assert_awaited_once_with(
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
        photos_use_case.list_categories.side_effect = MediaItem.NotFound
        payload = {"file_id": str(file_id)}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.status_code == 404
        photos_use_case.list_categories.assert_awaited_once_with(
            user.id, file_id
        )


class TestListSharedLinks:
    url = "/photos/media_items/list_shared_links"

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


class TestPurge:
    url = "/photos/media_items/purge"

    async def test(
        self, client: TestClient, photos_use_case: MagicMock, user: User,
    ):
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url)
        # THEN
        photos_use_case.purge.assert_awaited_once_with(user.id)
        assert response.status_code == 200


class TestRestoreBatch:
    url = "/photos/media_items/restore_batch"

    async def test(
        self, client: TestClient, photos_use_case: MagicMock, user: User,
    ):
        # GIVEN
        items = [
            _make_media_item("img.jpeg", mediatype="image/jpeg"),
            _make_media_item("img.png", mediatype="image/png"),
        ]
        file_ids = [item.file_id for item in items]
        photos_use_case.restore_batch.return_value = items
        payload = {"file_ids": [str(file_id) for file_id in file_ids]}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        photos_use_case.restore_batch.assert_awaited_once_with(
            user.id, file_ids
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(items)
        assert response.json()["items"][0]["name"] == "img.jpeg"
        assert response.json()["items"][0]["thumbnail_url"] is not None
        assert response.json()["items"][1]["name"] == "img.png"
        assert response.json()["items"][1]["thumbnail_url"] is not None


class TestSetCategories:
    url = "/photos/media_items/set_categories"

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
        photos_use_case.set_categories.assert_awaited_once_with(
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
        photos_use_case.set_categories.side_effect = MediaItem.NotFound
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        photos_use_case.set_categories.assert_awaited_once_with(
            user.id, file_id, categories=[]
        )
        assert response.status_code == 404
        assert response.json() == MediaItemNotFound().as_dict()
