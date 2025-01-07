from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.infrastructure.database import SENTINEL_ID
from app.app.photos.domain import Album
from app.toolkit import timezone

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.photos.services import AlbumService

pytestmark = [pytest.mark.anyio]


class TestCreate:
    @mock.patch("app.app.photos.services.album.AlbumService.get_available_slug")
    async def test(
        self,
        get_available_slug_mock: MagicMock,
        album_service: AlbumService,
    ):
        # GIVEN
        title, owner_id, created_at = "New Album", uuid.uuid4(), timezone.now()
        db = cast(mock.MagicMock, album_service.db)
        get_available_slug_mock.return_value = "new-album"
        # WHEN
        album = await album_service.create(title, owner_id, created_at)
        # THEN
        assert album == db.album.save.return_value
        db.album.save.assert_awaited_once_with(
            Album(
                id=SENTINEL_ID,
                title=title,
                slug="new-album",
                owner_id=owner_id,
                created_at=created_at,
            )
        )


class TestGetAvailableSlug:
    async def test_slug_returned_as_is(self, album_service: AlbumService):
        # GIVEN
        owner_id, slug = uuid.uuid4(), "my-slug"
        db = cast(mock.MagicMock, album_service.db)
        db.album.exists_with_slug.return_value = False

        # WHEN
        result = await album_service.get_available_slug(owner_id, slug)

        # THEN
        assert result == slug
        db.album.exists_with_slug.assert_awaited_once_with(owner_id, slug)
        db.album.count_by_slug_pattern.assert_not_awaited()

    async def test_slug_returned_with_postfix(self, album_service: AlbumService):
        # GIVEN
        owner_id, slug = uuid.uuid4(), "my-slug"
        db = cast(mock.MagicMock, album_service.db)
        db.album.exists_with_slug.return_value = True
        db.album.count_by_slug_pattern.return_value = 1

        # WHEN
        result = await album_service.get_available_slug(owner_id, slug)

        # THEN
        assert result == "my-slug-2"
        db.album.exists_with_slug.assert_awaited_once_with(owner_id, slug)
        db.album.count_by_slug_pattern.assert_awaited_once_with(
            owner_id, f"{slug}-[[:digit:]]+$"
        )


class TestList:
    async def test(self, album_service: AlbumService):
        # GIVEN
        owner_id = uuid.uuid4()
        db = cast(mock.MagicMock, album_service.db)
        # WHEN
        result = await album_service.list_(owner_id, offset=0, limit=10)
        # THEN
        assert result == db.album.list_by_owner_id.return_value
        db.album.list_by_owner_id.assert_awaited_once_with(
            owner_id, offset=0, limit=10
        )
