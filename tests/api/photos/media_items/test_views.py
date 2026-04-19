from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast

import pytest

from app.api.photos.exceptions import (
    DownloadNotFound,
    MediaItemContentMetadataNotFound,
    MediaItemNotFound,
    ThumbnailUnavailable,
)
from app.api.photos.media_items.views import _make_thumbnail_ttl
from app.app.blobs.domain import Blob, BlobMetadata
from app.app.photos.domain import MediaItem
from app.app.photos.repositories.media_item import CountResult
from app.app.photos.services.media_item import DownloadMediaItem, DownloadSessionInfo
from app.cache import disk_cache
from app.toolkit import timezone
from app.toolkit.mediatypes import MediaType
from app.toolkit.metadata import Exif

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.users.domain import User
    from tests.api.conftest import TestClient

pytestmark = [pytest.mark.anyio]


def _make_media_item(
    name: str | None = None,
    media_type: str | None = None,
) -> MediaItem:
    return MediaItem(
        id=uuid.uuid7(),
        owner_id=uuid.uuid7(),
        blob_id=uuid.uuid7(),
        name=name or f"{uuid.uuid4().hex}.jpeg",
        size=12,
        media_type=media_type or MediaType.IMAGE_JPEG,
        chash=uuid.uuid4().hex,
        taken_at=None,
        created_at=timezone.now(),
        modified_at=timezone.now(),
        deleted_at=None,
    )


def _make_download_media_item(
    name: str,
    media_type: str = MediaType.IMAGE_JPEG,
) -> DownloadMediaItem:
    return DownloadMediaItem(
        storage_key=f"owner_id/photos/2026/04/20/{name}",
        name=name,
        media_type=media_type,
        size=12,
        modified_at=timezone.now(),
    )


class TestCount:
    url = "/photos/media_items/count"

    async def test(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        count_result = CountResult(total=4, deleted=2)
        media_item_use_case.count.return_value = count_result
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        media_item_use_case.count.assert_awaited_once_with(user.id)
        assert response.json() == {
            "total": count_result.total,
            "deleted": count_result.deleted,
        }
        assert response.status_code == 200


class TestDeleteBatch:
    url = "/photos/media_items/delete_batch"

    async def test(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        items = [
            _make_media_item("img.jpeg", media_type="image/jpeg"),
            _make_media_item("img.png", media_type="image/png"),
        ]
        ids = [item.id for item in items]
        media_item_use_case.delete_batch.return_value = items
        payload = {"ids": [str(id_) for id_ in ids]}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        media_item_use_case.delete_batch.assert_awaited_once_with(user.id, ids)
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(items)
        assert response.json()["items"][0]["name"] == "img.jpeg"
        assert response.json()["items"][0]["thumbnail_url"] is not None
        assert response.json()["items"][1]["name"] == "img.png"
        assert response.json()["items"][1]["thumbnail_url"] is not None


class TestDeleteImmediatelyBatch:
    url = "/photos/media_items/delete_immediately_batch"

    async def test(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        ids = [uuid.uuid7(), uuid.uuid7()]
        payload = {"ids": [str(id_) for id_ in ids]}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        media_item_use_case.delete_immediately_batch.assert_awaited_once_with(
            user.id, ids
        )
        assert response.status_code == 200


class TestDownload:
    def url(self, key: str) -> str:
        return f"/photos/media_items/download?key={key}"

    async def test(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        key = uuid.uuid7().hex
        item = _make_download_media_item("photo.jpg")
        media_item_use_case.get_download_session.return_value = (item,)
        media_item_use_case.download.return_value = iter([b"data"])
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url(key))
        # THEN
        assert response.status_code == 200
        assert response.headers["Content-Disposition"] == (
            'attachment; filename="photo.jpg"'
        )
        assert response.headers["Content-Length"] == str(item.size)
        assert response.headers["Content-Type"] == item.media_type
        assert response.content == b"data"
        media_item_use_case.get_download_session.assert_awaited_once_with(key)
        media_item_use_case.download.assert_called_once_with(item)

    async def test_when_key_is_invalid(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        key = uuid.uuid4().hex
        media_item_use_case.get_download_session.return_value = None
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url(key))
        # THEN
        assert response.status_code == 404
        assert response.json() == DownloadNotFound().as_dict()
        media_item_use_case.get_download_session.assert_awaited_once_with(key)
        media_item_use_case.download.assert_not_called()

    async def test_when_session_contains_multiple_items(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        key = uuid.uuid4().hex
        media_item_use_case.get_download_session.return_value = (
            _make_download_media_item("photo.jpg"),
            _make_download_media_item("scan.png", media_type=MediaType.IMAGE_PNG),
        )
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url(key))
        # THEN
        assert response.status_code == 404
        assert response.json() == DownloadNotFound().as_dict()
        media_item_use_case.get_download_session.assert_awaited_once_with(key)
        media_item_use_case.download.assert_not_called()


class TestDownloadBatch:
    def url(self, key: str) -> str:
        return f"/photos/media_items/download_batch?key={key}"

    async def test(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        key = uuid.uuid4().hex
        session = (
            _make_download_media_item("photo.jpg"),
            _make_download_media_item("scan.png", media_type=MediaType.IMAGE_PNG),
        )
        media_item_use_case.get_download_session.return_value = session
        media_item_use_case.download_batch.return_value = iter([b"zip-bytes"])
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url(key))
        # THEN
        assert response.status_code == 200
        assert response.headers["Content-Disposition"] == (
            'attachment; filename="Shelf Cloud.zip"'
        )
        assert response.headers["Content-Type"] == "attachment/zip"
        assert response.content == b"zip-bytes"
        media_item_use_case.get_download_session.assert_awaited_once_with(key)
        media_item_use_case.download_batch.assert_called_once_with(session)

    async def test_when_key_is_invalid(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        key = uuid.uuid4().hex
        media_item_use_case.get_download_session.return_value = None
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url(key))
        # THEN
        assert response.status_code == 404
        assert response.json() == DownloadNotFound().as_dict()
        media_item_use_case.get_download_session.assert_awaited_once_with(key)
        media_item_use_case.download_batch.assert_not_called()

    async def test_when_session_contains_single_item(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        key = uuid.uuid4().hex
        media_item_use_case.get_download_session.return_value = (
            _make_download_media_item("photo.jpg"),
        )
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url(key))
        # THEN
        assert response.status_code == 404
        assert response.json() == DownloadNotFound().as_dict()
        media_item_use_case.get_download_session.assert_awaited_once_with(key)
        media_item_use_case.download_batch.assert_not_called()


class TestGetDownloadURL:
    url = "/photos/media_items/get_download_url"

    async def test_single_item_returns_single_download_url(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        media_item_id = uuid.uuid7()
        key = uuid.uuid4().hex
        media_item_use_case.create_download_session.return_value = DownloadSessionInfo(
            key=key,
            items_count=1,
        )
        payload = {"ids": [str(media_item_id)]}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.status_code == 200
        assert response.json() == {
            "download_url": (
                f"http://test/photos/media_items/download?key={key}"
            )
        }
        media_item_use_case.create_download_session.assert_awaited_once_with(
            user.id, [media_item_id]
        )

    async def test_multiple_items_return_batch_download_url(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        ids = [uuid.uuid7(), uuid.uuid7()]
        key = uuid.uuid4().hex
        media_item_use_case.create_download_session.return_value = DownloadSessionInfo(
            key=key,
            items_count=2,
        )
        payload = {"ids": [str(id_) for id_ in ids]}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.status_code == 200
        assert response.json() == {
            "download_url": (
                f"http://test/photos/media_items/download_batch?key={key}"
            )
        }
        media_item_use_case.create_download_session.assert_awaited_once_with(
            user.id, ids
        )

    async def test_filtered_items_can_return_single_download_url(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        ids = [uuid.uuid7(), uuid.uuid7()]
        key = uuid.uuid4().hex
        media_item_use_case.create_download_session.return_value = DownloadSessionInfo(
            key=key,
            items_count=1,
        )
        payload = {"ids": [str(id_) for id_ in ids]}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.status_code == 200
        assert response.json() == {
            "download_url": (
                f"http://test/photos/media_items/download?key={key}"
            )
        }
        media_item_use_case.create_download_session.assert_awaited_once_with(
            user.id, ids
        )

    async def test_when_media_item_is_missing(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        media_item_id = uuid.uuid7()
        media_item_use_case.create_download_session.side_effect = MediaItem.NotFound
        payload = {"ids": [str(media_item_id)]}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.status_code == 404
        assert response.json() == MediaItemNotFound().as_dict()
        media_item_use_case.create_download_session.assert_awaited_once_with(
            user.id, [media_item_id]
        )


class TestGetContentMetadata:
    url = "/photos/media_items/get_content_metadata"

    async def test(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        item = _make_media_item("photo.jpg", media_type=MediaType.IMAGE_JPEG)
        metadata = BlobMetadata(
            blob_id=item.blob_id,
            data=Exif(
                make="Apple",
                model="iPhone 16",
                width=4032,
                height=3024,
            ),
        )
        media_item_use_case.get_content_metadata.return_value = metadata
        payload = {"media_item_id": str(item.id)}

        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)

        # THEN
        assert response.status_code == 200
        assert response.json() == {
            "media_item_id": str(item.id),
            "data": {
                "type": "exif",
                "make": "Apple",
                "model": "iPhone 16",
                "focal_length": None,
                "focal_length_35mm": None,
                "fnumber": None,
                "exposure": None,
                "iso": None,
                "dt_original": None,
                "dt_digitized": None,
                "height": 3024,
                "width": 4032,
            },
        }
        media_item_use_case.get_content_metadata.assert_awaited_once_with(
            user.id, item.id
        )

    async def test_when_media_item_does_not_exist(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        media_item_id = uuid.uuid7()
        media_item_use_case.get_content_metadata.side_effect = MediaItem.NotFound
        payload = {"media_item_id": str(media_item_id)}

        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)

        # THEN
        assert response.status_code == 404
        assert response.json() == MediaItemNotFound().as_dict()
        media_item_use_case.get_content_metadata.assert_awaited_once_with(
            user.id, media_item_id
        )

    async def test_when_metadata_is_missing(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        media_item_id = uuid.uuid7()
        media_item_use_case.get_content_metadata.side_effect = BlobMetadata.NotFound
        payload = {"media_item_id": str(media_item_id)}

        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)

        # THEN
        assert response.status_code == 404
        assert response.json() == MediaItemContentMetadataNotFound(
            media_item_id=media_item_id
        ).as_dict()
        media_item_use_case.get_content_metadata.assert_awaited_once_with(
            user.id, media_item_id
        )


class TestGetThumbnail:
    @staticmethod
    def url(media_item_id: uuid.UUID, *, size: str = "xs") -> str:
        return f"/photos/media_items/get_thumbnail/{media_item_id}?size={size}"

    async def test(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        item = _make_media_item("photo.jpg", media_type="image/jpeg")
        thumbnail = b"thumbnail"
        media_item_use_case.thumbnail.return_value = (
            item,
            thumbnail,
            MediaType.IMAGE_WEBP,
        )
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url(item.id))
        # THEN
        assert response.status_code == 200
        assert response.content == thumbnail
        assert response.headers["Content-Disposition"] == (
            'inline; filename="photo.jpg"'
        )
        assert response.headers["Content-Length"] == str(len(thumbnail))
        assert response.headers["Content-Type"] == "image/webp"
        assert response.headers["Cache-Control"] == (
            "private, max-age=31536000, no-transform"
        )
        media_item_use_case.thumbnail.assert_awaited_once_with(user.id, item.id, 72)

    async def test_cache_hits(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        item = _make_media_item("photo.jpg", media_type="image/jpeg")
        thumbnail = b"thumbnail"
        media_item_use_case.thumbnail.return_value = (
            item,
            thumbnail,
            MediaType.IMAGE_WEBP,
        )

        client.mock_user(user)
        with disk_cache.detect as detector:
            # WHEN hits for the first time
            response_1 = await client.get(self.url(item.id))
            # THEN cache miss
            assert response_1.status_code == 200
            assert detector.calls == {}
            # WHEN hits for the second time
            response_2 = await client.get(self.url(item.id))
            # THEN cache hit
            assert len(detector.calls_list) == 1
            cache_key, cache_values = detector.calls_list[0]
            assert cache_key == f"{item.id}:xs"
            assert cache_values["ttl"] == 604800
            assert cache_values["name"] == "simple"
            assert cache_values["template"] == "{media_item_id}:{size}"
            assert cache_values["value"].body == response_1.content

            assert response_1.status_code == response_2.status_code
            assert response_1.content == response_2.content
            media_item_use_case.thumbnail.assert_awaited_once()

    @pytest.mark.parametrize(["size", "ttl"], [
        ("xs", "7d"),
        ("lg", "24h"),
    ])
    async def test_ttl_depends_on_size(self, size: str, ttl: str):
        assert _make_thumbnail_ttl(size=cast(Any, size)) == ttl

    async def test_when_media_item_not_found(
        self,
        client: TestClient,
        media_item_use_case: MagicMock,
        user: User,
    ):
        # GIVEN
        media_item_id = uuid.uuid7()
        media_item_use_case.thumbnail.side_effect = MediaItem.NotFound
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url(media_item_id))
        # THEN
        assert response.status_code == 404
        assert response.json() == MediaItemNotFound().as_dict()

    async def test_when_thumbnail_unavailable(
        self,
        client: TestClient,
        media_item_use_case: MagicMock,
        user: User,
    ):
        # GIVEN
        media_item_id = uuid.uuid7()
        media_item_use_case.thumbnail.side_effect = Blob.ThumbnailUnavailable
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url(media_item_id))
        # THEN
        assert response.status_code == 400
        assert response.json() == ThumbnailUnavailable().as_dict()


class TestList:
    url = "/photos/media_items/list"

    async def test(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        items = [
            _make_media_item("img.jpeg", media_type="image/jpeg"),
            _make_media_item("img.svg", media_type="image/svg+xml"),
        ]
        media_item_use_case.list_.return_value = items
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        media_item_use_case.list_.assert_awaited_once_with(
            user.id, only_favourites=False, offset=0, limit=100
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(items)
        assert response.json()["items"][0]["name"] == "img.jpeg"
        assert response.json()["items"][0]["thumbnail_url"].endswith(
            f"/photos/media_items/get_thumbnail/{items[0].id}"
        )
        assert response.json()["items"][1]["name"] == "img.svg"
        assert response.json()["items"][1]["thumbnail_url"].endswith(
            f"/photos/media_items/get_thumbnail/{items[1].id}"
        )

    async def test_only_favourites(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # WHEN
        client.mock_user(user)
        response = await client.get(f"{self.url}?favourites=true&page=2&page_size=150")
        # THEN
        media_item_use_case.list_.assert_awaited_once_with(
            user.id,
            only_favourites=True,
            offset=150,
            limit=150,
        )
        assert response.status_code == 200


class TestMarkFavouriteBatch:
    url = "/photos/media_items/favourites/mark_batch"

    async def test(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        ids = [uuid.uuid7(), uuid.uuid7()]
        payload = {"ids": [str(id_) for id_ in ids]}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        media_item_use_case.mark_favourite_batch.assert_awaited_once_with(user.id, ids)
        assert response.status_code == 200


class TestListFavouriteIDs:
    url = "/photos/media_items/favourites/list"

    async def test(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        ids = [uuid.uuid7(), uuid.uuid7()]
        media_item_use_case.list_favourite_ids.return_value = ids
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        media_item_use_case.list_favourite_ids.assert_awaited_once_with(user.id)
        assert response.status_code == 200
        assert response.json() == {"ids": [str(id_) for id_ in ids]}


class TestListDeleted:
    url = "/photos/media_items/list_deleted"

    async def test(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        items = [
            _make_media_item("img.jpeg", media_type="image/jpeg"),
            _make_media_item("img.png", media_type="image/png"),
        ]
        media_item_use_case.list_deleted.return_value = items
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        media_item_use_case.list_deleted.assert_awaited_once_with(user.id)
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(items)
        assert response.json()["items"][0]["name"] == "img.jpeg"
        assert response.json()["items"][0]["thumbnail_url"] is not None
        assert response.json()["items"][1]["name"] == "img.png"
        assert response.json()["items"][1]["thumbnail_url"] is not None


class TestUnmarkFavouriteBatch:
    url = "/photos/media_items/favourites/unmark_batch"

    async def test(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        ids = [uuid.uuid7(), uuid.uuid7()]
        payload = {"ids": [str(id_) for id_ in ids]}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        media_item_use_case.unmark_favourite_batch.assert_awaited_once_with(
            user.id,
            ids,
        )
        assert response.status_code == 200


class TestListCategories:
    url = "/photos/media_items/list_categories"

    async def test(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        media_item_id = uuid.uuid7()
        media_item_use_case.list_categories.return_value = [
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
        payload = {"media_item_id": str(media_item_id)}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.status_code == 200
        media_item_use_case.list_categories.assert_awaited_once_with(
            user.id, media_item_id
        )

    async def test_when_media_item_not_found(
        self,
        client: TestClient,
        media_item_use_case: MagicMock,
        user: User,
    ):
        # GIVEN
        media_item_id = uuid.uuid7()
        media_item_use_case.list_categories.side_effect = MediaItem.NotFound
        payload = {"media_item_id": str(media_item_id)}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.status_code == 404
        media_item_use_case.list_categories.assert_awaited_once_with(
            user.id, media_item_id
        )


class TestPurge:
    url = "/photos/media_items/purge"

    async def test(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url)
        # THEN
        media_item_use_case.purge.assert_awaited_once_with(user.id)
        assert response.status_code == 200


class TestRestoreBatch:
    url = "/photos/media_items/restore_batch"

    async def test(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        items = [
            _make_media_item("img.jpeg", media_type="image/jpeg"),
            _make_media_item("img.png", media_type="image/png"),
        ]
        ids = [item.id for item in items]
        media_item_use_case.restore_batch.return_value = items
        payload = {"ids": [str(id_) for id_ in ids]}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        media_item_use_case.restore_batch.assert_awaited_once_with(user.id, ids)
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(items)
        assert response.json()["items"][0]["name"] == "img.jpeg"
        assert response.json()["items"][0]["thumbnail_url"] is not None
        assert response.json()["items"][1]["name"] == "img.png"
        assert response.json()["items"][1]["thumbnail_url"] is not None


class TestSetCategories:
    url = "/photos/media_items/set_categories"

    async def test(
        self, client: TestClient, media_item_use_case: MagicMock, user: User
    ):
        # GIVEN
        media_item_id = uuid.uuid7()
        categories = [
            MediaItem.Category.Name.ANIMALS,
            MediaItem.Category.Name.PETS,
        ]
        payload = {
            "media_item_id": str(media_item_id),
            "categories": categories,
        }
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        media_item_use_case.set_categories.assert_awaited_once_with(
            user.id, media_item_id, categories=categories
        )
        assert response.status_code == 200

    async def test_when_media_item_not_found(
        self,
        client: TestClient,
        media_item_use_case: MagicMock,
        user: User,
    ):
        # GIVEN
        media_item_id = uuid.uuid7()
        payload = {
            "media_item_id": str(media_item_id),
            "categories": [],
        }
        media_item_use_case.set_categories.side_effect = MediaItem.NotFound
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        media_item_use_case.set_categories.assert_awaited_once_with(
            user.id, media_item_id, categories=[]
        )
        assert response.status_code == 404
        assert response.json() == MediaItemNotFound().as_dict()


class TestUpload:
    url = "/photos/media_items/upload"

    async def test(
        self, client: TestClient, media_item_use_case: MagicMock, user: User,
    ):
        # GIVEN
        item = _make_media_item("photo.jpg", media_type=MediaType.IMAGE_JPEG)
        media_item_use_case.upload.return_value = item
        payload = {
            "file": (item.name, b"Dummy file", item.media_type),
        }
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, files=payload)
        # THEN
        assert response.status_code == 200
        assert response.json()["id"] == str(item.id)
        assert response.json()["name"] == item.name
        assert response.json()["thumbnail_url"].endswith(
            f"/photos/media_items/get_thumbnail/{item.id}"
        )
        call_args = media_item_use_case.upload.await_args
        assert len(call_args.args) == 0
        assert list(call_args.kwargs.keys()) == [
            "owner_id", "name", "content", "media_type"
        ]
        assert call_args.kwargs["owner_id"] == user.id
        assert call_args.kwargs["name"] == item.name
        assert call_args.kwargs["content"].filename == item.name
        assert call_args.kwargs["content"].content_type == item.media_type
        assert call_args.kwargs["media_type"] == item.media_type
