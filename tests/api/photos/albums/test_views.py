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


def _make_album(owner_id: UUID) -> Album:
    return Album(
        id=uuid.uuid4(),
        owner_id=owner_id,
        title="New Album",
        created_at=timezone.now(),
        cover=None,
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


class TestCreate:
    url = "/photos/albums/create"

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


class TestList:
    url = "/photos/albums/list"

    async def test(self, client: TestClient, album_use_case: MagicMock, user: User):
        # GIVEN
        albums = [
            _make_album(user.id),
            _make_album(user.id),
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
        return f"/photos/albums/{slug}/list_items"

    async def test(self, client: TestClient, album_use_case: MagicMock, user: User):
        # GIVEN
        album = _make_album(user.id)
        items = [_make_media_item() for _ in range(3)]
        album_use_case.list_items.return_value = album, items
        client.mock_user(user)

        # WHEN
        response = await client.get(self.url(album.slug))

        # THEN
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(items)
        album_use_case.list_items.assert_awaited_once_with(
            user.id, album.slug, offset=0, limit=100
        )
