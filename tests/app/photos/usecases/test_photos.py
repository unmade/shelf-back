from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, TypeVar, cast
from unittest import mock

import pytest

from app.app.files.domain import SharedLink
from app.app.photos.domain import MediaItem
from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from app.app.photos.usecases import PhotosUseCase

pytestmark = [pytest.mark.anyio]

T = TypeVar("T")


def _make_media_item(
    name: str | None = None, mediatype: str | None = None
) -> MediaItem:
    return MediaItem(
        file_id=uuid.uuid4(),
        name=name or f"{uuid.uuid4().hex}.jpeg",
        size=12,
        mediatype=mediatype or MediaType.IMAGE_JPEG,  # type: ignore
    )


def _make_shared_link(file_id: UUID) -> SharedLink:
    return SharedLink(
        id=uuid.uuid4(),
        file_id=file_id,
        token=uuid.uuid4().hex,
    )


class TestAutoAddCategoryBatch:
    async def test(self, photos_use_case: PhotosUseCase):
        # GIVEN
        file_id = uuid.uuid4()
        categories = [
            (MediaItem.Category.Name.ANIMALS, 92),
            (MediaItem.Category.Name.PETS, 94),
        ]
        media_item_service = cast(mock.MagicMock, photos_use_case.media_item)
        # WHEN
        await photos_use_case.auto_add_category_batch(file_id, categories)
        # THEN
        media_item_service.auto_add_category_batch.assert_awaited_once_with(
            file_id, categories=categories
        )


class TestCountMediaItems:
    async def test(self, photos_use_case: PhotosUseCase):
        # GIVEN
        user_id = uuid.uuid4()
        media_item_service = cast(mock.MagicMock, photos_use_case.media_item)
        # WHEN
        result = await photos_use_case.count_media_items(user_id)
        # THEN
        assert result == media_item_service.count.return_value
        media_item_service.count.assert_awaited_once_with(user_id)


class TestDeleteMediaItemBatch:
    async def test(self, photos_use_case: PhotosUseCase):
        # GIVEN
        user_id = uuid.uuid4()
        file_ids = [uuid.uuid4(), uuid.uuid4()]
        media_item_service = cast(mock.MagicMock, photos_use_case.media_item)
        # WHEN
        result = await photos_use_case.delete_media_item_batch(user_id, file_ids)
        # THEN
        assert result == media_item_service.delete_batch.return_value
        media_item_service.delete_batch.assert_awaited_once_with(user_id, file_ids)


class TestEmptyTrash:
    @staticmethod
    def _aiter_items_factory(batches: list[list[T]]):
        async def _aiter_items(user_id: UUID) -> AsyncIterator[list[T]]:
            for batch in batches:
                yield batch
        return _aiter_items

    async def test(self, photos_use_case: PhotosUseCase):
        # GIVEN
        user_id = uuid.uuid4()
        items = [[_make_media_item(), _make_media_item()]]
        filecore = cast(mock.MagicMock, photos_use_case.filecore)
        media_item_service = cast(mock.MagicMock, photos_use_case.media_item)
        ns_service = cast(mock.MagicMock, photos_use_case.namespace)

        namespace = ns_service.get_by_owner_id.return_value
        media_item_service.iter_deleted = self._aiter_items_factory(items)
        file_ids = [item.file_id for item in items[0]]
        files = filecore.get_by_id_batch.return_value
        paths = [file.path for file in files]

        # WHEN
        await photos_use_case.empty_trash(user_id)

        # THEN
        ns_service.get_by_owner_id.assert_awaited_once_with(user_id)
        filecore.get_by_id_batch.assert_awaited_once_with(file_ids)
        filecore.delete_batch.assert_awaited_once_with(namespace.path, paths)


class TestDeleteMediaItemImmediatelyBatch:
    async def test(self, photos_use_case: PhotosUseCase):
        # GIVEN
        user_id = uuid.uuid4()
        filecore = cast(mock.MagicMock, photos_use_case.filecore)
        ns_service = cast(mock.MagicMock, photos_use_case.namespace)

        namespace = ns_service.get_by_owner_id.return_value
        file_ids = [uuid.uuid4(), uuid.uuid4()]
        files = filecore.get_by_id_batch.return_value
        paths = [file.path for file in files]

        # WHEN
        await photos_use_case.delete_media_item_immediately_batch(user_id, file_ids)

        # THEN
        ns_service.get_by_owner_id.assert_awaited_once_with(user_id)
        filecore.get_by_id_batch.assert_awaited_once_with(file_ids)
        filecore.delete_batch.assert_awaited_once_with(namespace.path, paths)


class TestListDeletedMediaItems:
    async def test(self, photos_use_case: PhotosUseCase):
        # GIVEN
        user_id = uuid.uuid4()
        media_item_service = cast(mock.MagicMock, photos_use_case.media_item)
        # WHEN
        result = await photos_use_case.list_deleted_media_items(user_id)
        # THEN
        assert result == media_item_service.list_deleted.return_value
        media_item_service.list_deleted.assert_awaited_once_with(
            user_id, offset=0, limit=2_000
        )


class TestListMediaItems:
    async def test(self, photos_use_case: PhotosUseCase):
        # GIVEN
        user_id = uuid.uuid4()
        media_item_service = cast(mock.MagicMock, photos_use_case.media_item)
        # WHEN
        result = await photos_use_case.list_media_items(user_id, offset=0, limit=25)
        # THEN
        assert result == media_item_service.list_for_user.return_value
        media_item_service.list_for_user.assert_awaited_once_with(
            user_id, only_favourites=False, offset=0, limit=25
        )


class TestListSharedLinks:
    async def test(self, photos_use_case: PhotosUseCase):
        # GIVEN
        user_id = uuid.uuid4()
        media_items = [_make_media_item() for _ in range(2)]
        file_ids = [item.file_id for item in media_items]
        links = [_make_shared_link(file_id) for file_id in file_ids + [uuid.uuid4()]]
        ns_service = cast(mock.MagicMock, photos_use_case.namespace)
        media_item_service = cast(mock.MagicMock, photos_use_case.media_item)
        media_item_service.get_by_id_batch.return_value = media_items
        sharing_service = cast(mock.MagicMock, photos_use_case.sharing)
        sharing_service.list_links_by_ns.return_value = links
        # WHEN
        result = await photos_use_case.list_shared_links(user_id)
        # THEN
        assert result == list(zip(media_items, links, strict=False))
        ns_service.get_by_owner_id.assert_awaited_once_with(user_id)
        namespace = ns_service.get_by_owner_id.return_value
        sharing_service.list_links_by_ns.assert_awaited_once_with(
            namespace.path, limit=1000
        )
        media_item_service.get_by_id_batch.assert_awaited_once_with(
            [link.file_id for link in links]
        )


class TestListMediaItemCategories:
    async def test(self, photos_use_case: PhotosUseCase):
        # GIVEN
        user_id, file_id = uuid.uuid4(), uuid.uuid4()
        media_item_service = cast(mock.MagicMock, photos_use_case.media_item)
        # WHEN
        result = await photos_use_case.list_media_item_categories(user_id, file_id)
        # THEN
        assert result == media_item_service.list_categories.return_value
        media_item_service.get_for_user.assert_awaited_once_with(user_id, file_id)
        item = media_item_service.get_for_user.return_value
        media_item_service.list_categories.assert_awaited_once_with(item.file_id)


class TestRestoreMediaItemBatch:
    async def test(self, photos_use_case: PhotosUseCase):
        # GIVEN
        user_id = uuid.uuid4()
        file_ids = [uuid.uuid4(), uuid.uuid4()]
        media_item_service = cast(mock.MagicMock, photos_use_case.media_item)
        # WHEN
        result = await photos_use_case.restore_media_item_batch(user_id, file_ids)
        # THEN
        assert result == media_item_service.restore_batch.return_value
        media_item_service.restore_batch.assert_awaited_once_with(user_id, file_ids)


class TestSetCategories:
    async def test(self, photos_use_case: PhotosUseCase):
        # GIVEN
        user_id, file_id = uuid.uuid4(), uuid.uuid4()
        media_item_service = cast(mock.MagicMock, photos_use_case.media_item)
        categories = [MediaItem.Category.Name.ANIMALS, MediaItem.Category.Name.PETS]
        # WHEN
        await photos_use_case.set_media_item_categories(
            user_id, file_id, categories=categories
        )
        # THEN
        media_item_service.get_for_user.assert_awaited_once_with(user_id, file_id)
        item = media_item_service.get_for_user.return_value
        media_item_service.set_categories.assert_awaited_once_with(
            item.file_id, categories
        )
