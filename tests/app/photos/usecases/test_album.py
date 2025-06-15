from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

if TYPE_CHECKING:
    from app.app.photos.usecases import AlbumUseCase

pytestmark = [pytest.mark.anyio]


class TestCreate:
    async def test(self, album_use_case: AlbumUseCase):
        # GIVEN
        title, owner_id = "New Album", uuid.uuid4()
        album_service = cast(mock.MagicMock, album_use_case.album)
        # WHEN
        result = await album_use_case.create(title, owner_id=owner_id)
        # THEN
        assert result == album_service.create.return_value
        album_service.create.assert_awaited_once_with(
            title=title,
            owner_id=owner_id,
            created_at=mock.ANY,
        )


class TestGetBySlug:
    async def test(self, album_use_case: AlbumUseCase):
        # GIVEN
        owner_id, slug = uuid.uuid4(), "new-album"
        album_service = cast(mock.MagicMock, album_use_case.album)
        # WHEN
        result = await album_use_case.get_by_slug(owner_id, slug)
        # THEN
        assert result == album_service.get_by_slug.return_value
        album_service.get_by_slug.assert_awaited_once_with(owner_id, slug)


class TestList:
    async def test(self, album_use_case: AlbumUseCase):
        # GIVEN
        owner_id = uuid.uuid4()
        album_service = cast(mock.MagicMock, album_use_case.album)
        # WHEN
        result = await album_use_case.list_(owner_id, offset=0, limit=10)
        # THEN
        assert result == album_service.list_.return_value
        album_service.list_.assert_awaited_once_with(
            owner_id, offset=0, limit=10
        )


class TestListItems:
    async def test(self, album_use_case: AlbumUseCase):
        # GIVEN
        owner_id, slug = uuid.uuid4(), "new-album"
        album_service = cast(mock.MagicMock, album_use_case.album)
        album_items = album_service.list_items.return_value
        # WHEN
        result = await album_use_case.list_items(owner_id, slug, offset=100, limit=200)
        # THEN
        assert result == album_items
        album_service.list_items.assert_awaited_once_with(
            owner_id, slug, offset=100, limit=200
        )
