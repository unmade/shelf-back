from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.app.photos.domain import Album, MediaItem
from app.toolkit import timezone
from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from unittest.mock import MagicMock
    from uuid import UUID

    from app.app.users.domain import User
    from tests.api.conftest import TestClient


def _make_album(owner_id: UUID, *, cover_id: UUID | None = None) -> Album:
    return Album(
        id=uuid.uuid4(),
        owner_id=owner_id,
        title="New Album",
        created_at=timezone.now(),
        cover=Album.Cover(file_id=cover_id) if cover_id else None,
    )


def _make_media_item(
    name: str | None = None, mediatype: str | None = None
) -> MediaItem:
    return MediaItem(
        file_id=uuid.uuid4(),
        name=name or f"{uuid.uuid4().hex}.jpeg",
        size=12,
        mediatype=mediatype or MediaType.IMAGE_JPEG,  # type: ignore
    )


class TestAddItems:
    url = "/photos/albums/{slug}/items"

    async def test(self, client: TestClient, album_use_case: MagicMock, user: User):
        # GIVEN
        album = _make_album(user.id)
        album_use_case.add_album_items.return_value = album
        items = [_make_media_item() for _ in range(3)]
        file_ids = [item.file_id for item in items]
        payload = {"file_ids": [str(file_id) for file_id in file_ids]}
        client.mock_user(user)
        # WHEN
        response = await client.put(self.url.format(slug=album.slug), json=payload)
        # THEN
        assert response.status_code == 200
        album_use_case.add_album_items.assert_awaited_once_with(
            user.id, album.slug, file_ids=file_ids
        )

    async def test_when_album_not_found(
        self, client: TestClient, album_use_case: MagicMock, user: User
    ):
        # GIVEN
        album = _make_album(user.id)
        album_use_case.add_album_items.side_effect = Album.NotFound()
        file_ids = [uuid.uuid4() for _ in range(2)]
        payload = {"file_ids": [str(file_id) for file_id in file_ids]}
        client.mock_user(user)
        # WHEN
        response = await client.put(self.url.format(slug=album.slug), json=payload)
        # THEN
        assert response.status_code == 404
        album_use_case.add_album_items.assert_awaited_once_with(
            user.id, album.slug, file_ids=file_ids
        )


class TestCreate:
    url = "/photos/albums"

    async def test(self, client: TestClient, album_use_case: MagicMock, user: User):
        # GIVEN
        album = _make_album(user.id)
        album_use_case.create.return_value = album
        payload = {"title": album.title}
        # WHEN
        client.mock_user(user)
        response = await client.post(self.url, json=payload)
        # THEN
        assert response.json()["title"] == album.title
        assert response.status_code == 200
        album_use_case.create.assert_awaited_once_with(
            title=album.title, owner_id=user.id
        )


class TestDelete:
    url = "/photos/albums/{slug}"

    async def test(self, client: TestClient, album_use_case: MagicMock, user: User):
        # GIVEN
        album = _make_album(user.id)
        album_use_case.delete.return_value = album
        client.mock_user(user)
        # WHEN
        response = await client.delete(self.url.format(slug=album.slug))
        # THEN
        assert response.status_code == 200
        album_use_case.delete.assert_awaited_once_with(user.id, album.slug)

    async def test_when_album_not_found(
        self, client: TestClient, album_use_case: MagicMock, user: User
    ):
        # GIVEN
        album = _make_album(user.id)
        album_use_case.delete.side_effect = Album.NotFound()
        client.mock_user(user)
        # WHEN
        response = await client.delete(self.url.format(slug=album.slug))
        # THEN
        assert response.status_code == 404
        album_use_case.delete.assert_awaited_once_with(user.id, album.slug)


class TestGetAlbum:
    url = "/photos/albums/{slug}"

    async def test(self, client: TestClient, album_use_case: MagicMock, user: User):
        # GIVEN
        album = _make_album(user.id)
        album_use_case.get_by_slug.return_value = album
        client.mock_user(user)
        # WHEN
        response = await client.get(self.url.format(slug=album.slug))
        # THEN
        assert response.status_code == 200
        assert response.json()["title"] == album.title
        album_use_case.get_by_slug.assert_awaited_once_with(user.id, album.slug)

    async def test_when_does_not_exist(
        self, client: TestClient, album_use_case: MagicMock, user: User
    ):
        # GIVEN
        album_use_case.get_by_slug.side_effect = Album.NotFound()
        client.mock_user(user)
        # WHEN
        response = await client.get(self.url.format(slug="non-existent-album"))
        # THEN
        assert response.status_code == 404
        album_use_case.get_by_slug.assert_awaited_once_with(
            user.id, "non-existent-album"
        )


class TestList:
    url = "/photos/albums"

    async def test(self, client: TestClient, album_use_case: MagicMock, user: User):
        # GIVEN
        albums = [
            _make_album(user.id),
            _make_album(user.id, cover_id=uuid.uuid4()),
        ]
        album_use_case.list_.return_value = albums
        # WHEN
        client.mock_user(user)
        response = await client.get(self.url)
        # THEN
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(albums)
        album_use_case.list_.assert_awaited_once_with(user.id, offset=0, limit=100)


class TestListAlbumItems:
    @staticmethod
    def url(slug: str) -> str:
        return f"/photos/albums/{slug}/items"

    async def test(self, client: TestClient, album_use_case: MagicMock, user: User):
        # GIVEN
        album = _make_album(user.id)
        items = [_make_media_item() for _ in range(3)]
        album_use_case.list_items.return_value = items
        client.mock_user(user)

        # WHEN
        response = await client.get(self.url(album.slug))

        # THEN
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(items)
        album_use_case.list_items.assert_awaited_once_with(
            user.id, album.slug, offset=0, limit=100
        )


class TestRemoveItems:
    url = "/photos/albums/{slug}/items"

    async def test(self, client: TestClient, album_use_case: MagicMock, user: User):
        # GIVEN
        album = _make_album(user.id)
        album_use_case.remove_album_items.return_value = album
        items = [_make_media_item() for _ in range(3)]
        file_ids = [item.file_id for item in items]
        payload = {"file_ids": [str(file_id) for file_id in file_ids]}
        client.mock_user(user)
        # WHEN
        # see: https://www.python-httpx.org/compatibility/#request-body-on-http-methods
        response = await client.request(
            "DELETE", self.url.format(slug=album.slug), json=payload
        )
        # THEN
        assert response.status_code == 200
        album_use_case.remove_album_items.assert_awaited_once_with(
            user.id, album.slug, file_ids=file_ids
        )

    async def test_when_album_not_found(
        self, client: TestClient, album_use_case: MagicMock, user: User
    ):
        # GIVEN
        album = _make_album(user.id)
        album_use_case.remove_album_items.side_effect = Album.NotFound()
        file_ids = [uuid.uuid4() for _ in range(2)]
        payload = {"file_ids": [str(file_id) for file_id in file_ids]}
        client.mock_user(user)
        # WHEN
        response = await client.request(
            "DELETE", self.url.format(slug=album.slug), json=payload
        )
        # THEN
        assert response.status_code == 404
        album_use_case.remove_album_items.assert_awaited_once_with(
            user.id, album.slug, file_ids=file_ids
        )
