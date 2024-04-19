from __future__ import annotations

import operator
from typing import TYPE_CHECKING

import pytest

from app.app.infrastructure.database import SENTINEL_ID
from app.app.photos.domain import Album
from app.infrastructure.database.edgedb.repositories import AlbumRepository
from app.toolkit import timezone

if TYPE_CHECKING:
    from app.app.users.domain import User
    from tests.infrastructure.database.edgedb.conftest import AlbumFactory

pytestmark = [pytest.mark.anyio, pytest.mark.database]


class TestListByOwnerID:
    @pytest.mark.usefixtures("namespace")
    async def test(
        self,
        album_repo: AlbumRepository,
        album_factory: AlbumFactory,
        user: User,
    ):
        # GIVEN
        albums = [await album_factory(user.id) for _ in range(5)]
        # WHEN
        result = await album_repo.list_by_owner_id(user.id, offset=0)
        # THEN
        assert result == sorted(albums, key=operator.attrgetter("title"))

        # WHEN
        result = await album_repo.list_by_owner_id(user.id, offset=2, limit=2)
        # THEN
        assert result == sorted(albums, key=operator.attrgetter("title"))[2:4]

    @pytest.mark.usefixtures("namespace")
    async def test_when_empty(self, album_repo: AlbumRepository, user: User):
        # WHEN
        result = await album_repo.list_by_owner_id(user.id, offset=0)
        # THEN
        assert result == []


class TestSave:
    @pytest.mark.usefixtures("namespace")
    async def test(
        self,
        album_repo: AlbumRepository,
        user: User,
    ):
        # GIVEN
        entity = Album(
            id=SENTINEL_ID,
            title="New Album",
            owner_id=user.id,
            created_at=timezone.now(),
        )
        # WHEN
        result = await album_repo.save(entity)
        # THEN
        assert result.id != SENTINEL_ID
        assert result.title == entity.title
        assert result.created_at == entity.created_at
        assert result.owner_id == entity.owner_id
        assert result.cover is None
