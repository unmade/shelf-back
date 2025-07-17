from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.photos.domain import Album

if TYPE_CHECKING:
    from app.app.photos.usecases import AlbumUseCase

pytestmark = [pytest.mark.anyio]


class TestAddItems:
    async def test(self, album_use_case: AlbumUseCase):
        # GIVEN
        owner_id, slug = uuid.uuid4(), "new-album"
        file_ids = [uuid.uuid4() for _ in range(5)]
        album_service = cast(mock.MagicMock, album_use_case.album)
        # WHEN
        result = await album_use_case.add_album_items(owner_id, slug, file_ids)
        # THEN
        assert result == album_service.add_items.return_value
        album_service.add_items.assert_awaited_once_with(owner_id, slug, file_ids)

    async def test_sets_cover_if_not_set(self, album_use_case: AlbumUseCase):
        # GIVEN
        owner_id, slug = uuid.uuid4(), "new-album"
        file_ids = [uuid.uuid4() for _ in range(3)]
        album_service = cast(mock.MagicMock, album_use_case.album)
        album = album_service.add_items.return_value
        album.cover = None
        # WHEN
        result = await album_use_case.add_album_items(owner_id, slug, file_ids)
        # THEN
        album_service.add_items.assert_awaited_once_with(owner_id, slug, file_ids)
        album_service.set_cover.assert_awaited_once_with(owner_id, slug, file_ids[0])
        assert result == album_service.set_cover.return_value

    async def test_does_not_set_cover_if_already_set(
        self, album_use_case: AlbumUseCase
    ):
        # GIVEN
        owner_id, slug = uuid.uuid4(), "new-album"
        file_ids = [uuid.uuid4() for _ in range(2)]
        album_service = cast(mock.MagicMock, album_use_case.album)
        # WHEN
        await album_use_case.add_album_items(owner_id, slug, file_ids)
        # THEN
        album_service.set_cover.assert_not_awaited()


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

    async def test_when_album_does_not_exist(self, album_use_case: AlbumUseCase):
        # GIVEN
        owner_id, slug = uuid.uuid4(), "nonexistent-album"
        album_service = cast(mock.MagicMock, album_use_case.album)
        album_service.get_by_slug.side_effect = Album.NotFound()
        # WHEN / THEN
        with pytest.raises(Album.NotFound):
            await album_use_case.get_by_slug(owner_id, slug)


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


class TestRemoveItems:
    async def test(self, album_use_case: AlbumUseCase):
        # GIVEN
        owner_id, slug = uuid.uuid4(), "new-album"
        file_ids = [uuid.uuid4() for _ in range(5)]
        album_service = cast(mock.MagicMock, album_use_case.album)
        # WHEN
        await album_use_case.remove_album_items(owner_id, slug, file_ids)
        # THEN
        album_service.remove_items.assert_awaited_once_with(
            owner_id, slug, file_ids,
        )
        album_service.list_items.assert_not_awaited()
        album_service.set_cover.assert_not_awaited()
        album_service.clear_cover.assert_not_awaited()

    async def test_clears_cover_if_removed_items_includes_cover(
        self, album_use_case: AlbumUseCase
    ):
        # GIVEN
        owner_id, slug = uuid.uuid4(), "new-album"
        file_ids = [uuid.uuid4() for _ in range(2)]
        album_service = cast(mock.MagicMock, album_use_case.album)
        album = album_service.remove_items.return_value
        album.cover = mock.Mock(file_id=file_ids[0])
        album.items_count = 5
        # WHEN
        await album_use_case.remove_album_items(owner_id, slug, file_ids)
        # THEN
        album_service.list_items.assert_awaited_once_with(
            owner_id, slug, offset=0, limit=1
        )
        album_items = album_service.list_items.return_value
        album_service.set_cover.assert_awaited_once_with(
            owner_id, slug, album_items[0].file_id
        )

    async def test_clears_cover_if_no_items_left(
        self, album_use_case: AlbumUseCase
    ):
        # GIVEN
        owner_id, slug = uuid.uuid4(), "new-album"
        file_ids = [uuid.uuid4() for _ in range(2)]
        album_service = cast(mock.MagicMock, album_use_case.album)
        album = album_service.remove_items.return_value
        album.cover = mock.Mock(file_id=file_ids[0])
        album.items_count = 0
        # WHEN
        await album_use_case.remove_album_items(owner_id, slug, file_ids)
        # THEN
        album_service.list_items.assert_not_awaited()
        album_service.set_cover.assert_not_awaited()
        album_service.clear_cover.assert_awaited_once_with(owner_id, slug)

    async def test_when_album_does_not_exist(self, album_use_case: AlbumUseCase):
        # GIVEN
        owner_id, slug = uuid.uuid4(), "nonexistent-album"
        file_ids = [uuid.uuid4() for _ in range(2)]
        album_service = cast(mock.MagicMock, album_use_case.album)
        album_service.remove_items.side_effect = Album.NotFound()
        # WHEN / THEN
        with pytest.raises(Album.NotFound):
            await album_use_case.remove_album_items(owner_id, slug, file_ids)
