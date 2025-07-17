from __future__ import annotations

import operator
import uuid
from typing import TYPE_CHECKING, cast
from uuid import UUID

import pytest

from app.app.infrastructure.database import SENTINEL_ID
from app.app.photos.domain import Album
from app.infrastructure.database.edgedb.db import db_context
from app.infrastructure.database.edgedb.repositories import AlbumRepository
from app.toolkit import timezone

if TYPE_CHECKING:
    from app.app.users.domain import User
    from tests.infrastructure.database.edgedb.conftest import (
        AlbumFactory,
        MediaItemFactory,
    )

pytestmark = [pytest.mark.anyio, pytest.mark.database]


async def _get_album_cover_id(album_id: UUID) -> UUID | None:
    query = """
        SELECT
            Album { cover }
        FILTER
            .id = <uuid>$album_id
        LIMIT 1
    """
    obj = await db_context.get().query_required_single(query, album_id=album_id)
    return obj.cover.id if obj.cover else None


async def _get_album_items_count(album_id: UUID) -> int:
    query = """
        SELECT
            Album { items_count }
        FILTER
            .id = <uuid>$album_id
        LIMIT 1
    """
    obj = await db_context.get().query_required_single(query, album_id=album_id)
    return cast(int, obj.items_count)


async def _list_item_ids(album_id: UUID) -> list[UUID]:
    query = """
        SELECT
            Album { items }
        FILTER
            .id = <uuid>$album_id
        LIMIT 1
    """
    obj = await db_context.get().query_required_single(query, album_id=album_id)
    return sorted(item.id for item in obj.items)


class TestAddItems:
    @pytest.mark.usefixtures("namespace")
    async def test(
        self,
        album_repo: AlbumRepository,
        album_factory: AlbumFactory,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        max_items = 5
        items = [await media_item_factory(user.id) for _ in range(max_items)]
        album = await album_factory(user.id, title="album", items=items[:2])
        file_ids = sorted(item.file_id for item in items[2:])
        # WHEN
        await album_repo.add_items(user.id, album.slug, file_ids=file_ids)
        # THEN
        assert await _list_item_ids(album.id) == [item.file_id for item in items]
        assert await _get_album_items_count(album.id) == max_items


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


class TestGetBySlug:
    @pytest.mark.usefixtures("namespace")
    async def test(
        self,
        album_repo: AlbumRepository,
        album_factory: AlbumFactory,
        user: User,
    ):
        # GIVEN
        album = await album_factory(user.id, title="album")
        # WHEN
        result = await album_repo.get_by_slug(user.id, album.slug)
        # THEN
        assert result == album

    @pytest.mark.usefixtures("namespace")
    async def test_when_not_found(
        self,
        album_repo: AlbumRepository,
        album_factory: AlbumFactory,
        user: User,
    ):
        # GIVEN
        await album_factory(user.id, title="album")
        # WHEN
        with pytest.raises(Album.NotFound):
            await album_repo.get_by_slug(user.id, "non-existing")


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


class TestListByAlbum:
    @pytest.mark.usefixtures("namespace")
    async def test(
        self,
        album_repo: AlbumRepository,
        album_factory: AlbumFactory,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        items = list(reversed([await media_item_factory(user.id) for _ in range(20)]))
        album_a = await album_factory(user.id, items=items[:10])
        album_b = await album_factory(user.id, items=items[15:])
        # WHEN
        result = await album_repo.list_items(user.id, album_a.slug, offset=0)
        # THEN
        assert result == items[:10]

        # WHEN
        result = await album_repo.list_items(user.id, album_a.slug, offset=5, limit=10)
        # THEN
        assert result == items[5:10]

        # WHEN
        result = await album_repo.list_items(user.id, album_b.slug, offset=0)
        assert result == items[15:]


class TestRemoveItems:
    @pytest.mark.usefixtures("namespace")
    async def test(
        self,
        album_repo: AlbumRepository,
        album_factory: AlbumFactory,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        items = [await media_item_factory(user.id) for _ in range(5)]
        album = await album_factory(user.id, title="album", items=items)
        file_ids = sorted(item.file_id for item in items[:2])
        # WHEN
        await album_repo.remove_items(user.id, album.slug, file_ids=file_ids)
        # THEN
        expected_ids = sorted(item.file_id for item in items[2:])
        assert await _list_item_ids(album.id) == expected_ids
        assert await _get_album_items_count(album.id) == 3


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


class TestSetCover:
    @pytest.mark.usefixtures("namespace")
    async def test(
        self,
        album_repo: AlbumRepository,
        album_factory: AlbumFactory,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        items = [await media_item_factory(user.id) for _ in range(2)]
        album = await album_factory(user.id, title="album", items=items)
        # WHEN
        await album_repo.set_cover(user.id, album.slug, items[1].file_id)
        # THEN
        cover_id = await _get_album_cover_id(album.id)
        assert cover_id == items[1].file_id

    @pytest.mark.usefixtures("namespace")
    async def test_when_album_does_not_exist(
        self,
        album_repo: AlbumRepository,
        user: User,
    ):
        # GIVEN
        file_ids = [uuid.uuid4() for _ in range(2)]
        # WHEN / THEN
        with pytest.raises(Album.NotFound):
            await album_repo.set_cover(user.id, "non-existing-album", file_ids[1])
