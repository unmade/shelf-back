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


class TestCountBySlugPattern:
    @pytest.mark.usefixtures("namespace")
    async def test(
        self,
        album_repo: AlbumRepository,
        album_factory: AlbumFactory,
        user: User,
    ):
        # GIVEN
        pattern = "album-[[:digit:]]+$"
        await album_factory(user.id, title="album-1")
        await album_factory(user.id, title="album-2")
        # WHEN
        result = await album_repo.count_by_slug_pattern(user.id, pattern)
        # THEN
        assert result == 2

    @pytest.mark.usefixtures("namespace")
    async def test_when_no_match_found(
        self,
        album_repo: AlbumRepository,
        album_factory: AlbumFactory,
        user: User,
    ):
        # GIVEN
        pattern = "album-[[:digit:]]+$"
        await album_factory(user.id, title="album")
        # WHEN
        result = await album_repo.count_by_slug_pattern(user.id, pattern)
        # THEN
        assert result == 0


class TestExistsWithSlug:
    async def test(
        self,
        album_repo: AlbumRepository,
        album_factory: AlbumFactory,
        user: User,
    ):
        # GIVEN
        await album_factory(user.id, title="album")
        # WHEN
        result = await album_repo.exists_with_slug(user.id, "album")
        # THEN
        assert result is True

        # WHEN
        result = await album_repo.exists_with_slug(user.id, "non-existing")
        # THEN
        assert result is False


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
