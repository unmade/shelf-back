from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.infrastructure.database import SENTINEL_ID
from app.app.photos.domain import Album
from app.toolkit import timezone

if TYPE_CHECKING:
    from app.app.photos.services import AlbumService

pytestmark = [pytest.mark.anyio]


class TestCreate:
    async def test(self, album_service: AlbumService):
        # GIVEN
        title, owner_id, created_at = "New Album", uuid.uuid4(), timezone.now()
        db = cast(mock.MagicMock, album_service.db)
        # WHEN
        album = await album_service.create(title, owner_id, created_at)
        # THEN
        assert album == db.album.save.return_value
        db.album.save.assert_awaited_once_with(
            Album(
                id=SENTINEL_ID,
                title=title,
                owner_id=owner_id,
                created_at=created_at,
            )
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
