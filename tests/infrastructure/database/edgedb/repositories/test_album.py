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


async def _exists_with_slug(owner_id: UUID, slug: str) -> bool:
    query = """
        SELECT EXISTS(
            SELECT
                Album
            FILTER
                .owner.id = <uuid>$owner_id
                AND
                .slug = <str>$slug
            LIMIT 1
        )
    """
    return cast(
        bool,
        await db_context.get().query_required_single(
            query,
            owner_id=owner_id,
            slug=slug,
        )
    )


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
        result = await album_repo.add_items(user.id, album.slug, file_ids=file_ids)
        # THEN
        assert result.items_count == max_items
        assert await _get_album_items_count(album.id) == max_items
        assert await _list_item_ids(album.id) == [item.file_id for item in items]

    @pytest.mark.usefixtures("namespace")
    async def test_when_album_does_not_exist(
        self,
        album_repo: AlbumRepository,
        user: User,
    ):
        # GIVEN
        slug = "nonexistent-album"
        file_ids = [uuid.uuid4() for _ in range(2)]
        # WHEN / THEN
        with pytest.raises(Album.NotFound):
            await album_repo.add_items(user.id, slug, file_ids)


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


class TestDelete:
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
        result = await album_repo.delete(user.id, album.slug)
        # THEN
        assert await _exists_with_slug(user.id, album.slug) is False
        assert result.id == album.id

    @pytest.mark.usefixtures("namespace")
    async def test_when_does_not_exist(
        self,
        album_repo: AlbumRepository,
        user: User,
    ):
        # GIVEN
        slug = "non-existing-album"
        # WHEN / THEN
        with pytest.raises(Album.NotFound):
            await album_repo.delete(user.id, slug)


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
    async def test_when_does_not_exist(
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
        result = await album_repo.remove_items(user.id, album.slug, file_ids=file_ids)
        # THEN
        assert result.items_count == 3
        assert await _get_album_items_count(album.id) == 3
        expected_ids = sorted(item.file_id for item in items[2:])
        assert await _list_item_ids(album.id) == expected_ids

    @pytest.mark.usefixtures("namespace")
    async def test_when_album_does_not_exist(
        self,
        album_repo: AlbumRepository,
        user: User,
    ):
        # GIVEN
        slug = "nonexistent-album"
        file_ids = [uuid.uuid4() for _ in range(2)]
        # WHEN / THEN
        with pytest.raises(Album.NotFound):
            await album_repo.remove_items(user.id, slug, file_ids)


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
        items = [await media_item_factory(user.id) for _ in range(3)]
        album = await album_factory(user.id, title="album", items=items)
        expected_cover_id = items[1].file_id
        # WHEN
        result = await album_repo.set_cover(user.id, album.slug, expected_cover_id)
        # THEN
        assert result.cover
        assert result.cover.file_id == expected_cover_id
        assert await _get_album_cover_id(album.id) == expected_cover_id

    @pytest.mark.usefixtures("namespace")
    async def test_sets_empty_cover(
        self,
        album_repo: AlbumRepository,
        album_factory: AlbumFactory,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        items = [await media_item_factory(user.id) for _ in range(3)]
        cover_file_id = items[1].file_id
        album = await album_factory(
            user.id, title="album", items=items, cover_file_id=cover_file_id
        )
        # WHEN
        result = await album_repo.set_cover(user.id, album.slug, file_id=None)
        # THEN
        assert result.cover is None
        assert await _get_album_cover_id(album.id) is None

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


class TestUpdate:
    @pytest.mark.usefixtures("namespace")
    async def test(
        self,
        album_repo: AlbumRepository,
        album_factory: AlbumFactory,
        user: User,
    ):
        # GIVEN
        album = await album_factory(user.id, title="Old Title")
        new_title, new_slug = "New Title", "new-title"
        # WHEN
        result = await album_repo.update(album, title=new_title, slug=new_slug)
        # THEN
        assert result.title == new_title
        assert result.slug == new_slug
        assert await _exists_with_slug(user.id, album.slug) is False
        assert await _exists_with_slug(user.id, new_slug) is True

    @pytest.mark.usefixtures("namespace")
    async def test_slug_is_not_changed(
        self,
        album_repo: AlbumRepository,
        album_factory: AlbumFactory,
        user: User,
    ):
        # GIVEN
        album = await album_factory(user.id, title="Old Title")
        new_title = "New Title"
        # WHEN
        result = await album_repo.update(album, title=new_title)
        # THEN
        assert result.title == new_title
        assert result.slug == "old-title"
        assert await _exists_with_slug(user.id, "old-title") is True

    @pytest.mark.usefixtures("namespace")
    async def test_when_album_does_not_exist(
        self,
        album_repo: AlbumRepository,
        user: User,
    ):
        # GIVEN
        album = Album(id=SENTINEL_ID, title="album", slug="album", owner_id=user.id)
        # WHEN / THEN
        with pytest.raises(Album.NotFound):
            await album_repo.update(album, title="New Title")
