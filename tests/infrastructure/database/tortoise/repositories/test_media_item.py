from __future__ import annotations

import operator
import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.photos.domain import MediaItem
from app.infrastructure.database.tortoise import models
from app.toolkit import timezone
from app.toolkit.mediatypes import MediaType
from app.toolkit.metadata import Exif

if TYPE_CHECKING:
    from app.app.users.domain import User
    from app.infrastructure.database.tortoise.repositories import MediaItemRepository
    from tests.infrastructure.database.tortoise.conftest import (
        BlobMetadataFactory,
        MediaItemFactory,
    )

pytestmark = [pytest.mark.anyio, pytest.mark.database]


class TestCount:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        await media_item_factory(user.id),
        await media_item_factory(user.id),
        await media_item_factory(user.id, deleted_at=timezone.now()),
        # WHEN
        result = await media_item_repo.count(user.id)
        # THEN
        assert result.total == 2
        assert result.deleted == 1


class TestDeleteBatch:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        items = [
            await media_item_factory(user.id),
            await media_item_factory(user.id),
            await media_item_factory(user.id),
        ]
        ids = [item.id for item in items[:2]]
        # WHEN
        await media_item_repo.delete_batch(ids)
        # THEN
        assert await models.MediaItem.filter(id__in=ids).count() == 0
        assert await models.MediaItem.filter(id=items[-1].id).exists() is True


class TestGetByID:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        media_item = await media_item_factory(user.id)
        # WHEN
        result = await media_item_repo.get_by_id(media_item.id)
        # THEN
        assert result == media_item

    async def test_when_media_item_does_not_exist(
        self, media_item_repo: MediaItemRepository,
    ):
        # GIVEN
        media_item_id = uuid.uuid7()
        # WHEN / THEN
        with pytest.raises(MediaItem.NotFound):
            await media_item_repo.get_by_id(media_item_id)


class TestGetByIDBatch:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        items = [
            await media_item_factory(user.id),
            await media_item_factory(user.id),
            await media_item_factory(user.id),
        ]
        ids = [item.id for item in items[:2]]
        # WHEN
        result = await media_item_repo.get_by_id_batch(ids)
        # THEN
        assert result == list(reversed(items[:2]))


class TestGetByUserID:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        media_item = await media_item_factory(user.id)
        # WHEN
        result = await media_item_repo.get_for_owner(user.id, media_item.id)
        # THEN
        assert result == media_item

    async def test_when_media_item_does_not_exist(
        self, media_item_repo: MediaItemRepository, user: User,
    ):
        media_item_id = uuid.uuid7()
        with pytest.raises(MediaItem.NotFound):
            await media_item_repo.get_for_owner(user.id, media_item_id)


class TestListByOwner:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        blob_metadata_factory: BlobMetadataFactory,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        await media_item_factory(user.id, deleted_at=timezone.now()),
        items = [
            await media_item_factory(user.id, "im.gif", media_type=MediaType.IMAGE_GIF),
            await media_item_factory(user.id, "im.png", media_type=MediaType.IMAGE_PNG),
        ]
        items[0].taken_at = timezone.now()
        await blob_metadata_factory(
            items[0].blob_id,
            Exif(dt_original=items[0].taken_at.timestamp()),
        )
        # WHEN
        result = await media_item_repo.list_by_owner(user.id, offset=0)
        # THEN
        assert result == [
            items[1],
            items[0],
        ]

    async def test_only_favourites(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        items = [
            await media_item_factory(
                user.id, "im.jpg", media_type=MediaType.IMAGE_JPEG
            ),
            await media_item_factory(user.id, "im.png", media_type=MediaType.IMAGE_PNG),
            await media_item_factory(
                user.id, "i.heic", media_type=MediaType.IMAGE_HEIC
            ),
        ]
        await models.MediaItemFavourite.create(
            user_id=user.id, media_item_id=items[0].id
        )
        await models.MediaItemFavourite.create(
            user_id=user.id, media_item_id=items[-1].id
        )
        # WHEN
        result = await media_item_repo.list_by_owner(
            user.id, only_favourites=True, offset=0
        )
        # THEN
        assert result == sorted(
            [items[0], items[-1]],
            key=operator.attrgetter("modified_at"),
            reverse=True,
        )

    async def test_only_favourites_when_its_empty(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        await media_item_factory(user.id, "im.jpg", media_type=MediaType.IMAGE_JPEG),
        await media_item_factory(user.id, "im.png", media_type=MediaType.IMAGE_PNG),
        # WHEN
        result = await media_item_repo.list_by_owner(
            user.id, only_favourites=True, offset=0
        )
        # THEN
        assert result == []


class TestListDeleted:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        items = [
            await media_item_factory(user.id, deleted_at=timezone.now()),
            await media_item_factory(user.id, deleted_at=timezone.now()),
            await media_item_factory(user.id, deleted_at=None),
        ]
        # WHEN
        result = await media_item_repo.list_deleted(user.id, offset=0)
        # THEN
        assert result == [items[1], items[0]]


class TestSetDeletedAtBatch:
    async def test(
        self,
        media_item_repo: MediaItemRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        deleted_at = timezone.now()
        items = [
            await media_item_factory(user.id, deleted_at=None),
            await media_item_factory(user.id, deleted_at=None),
        ]
        ids = [item.id for item in items]
        # WHEN
        result = await media_item_repo.set_deleted_at_batch(
            user.id, ids, deleted_at
        )
        # THEN
        assert result[0].deleted_at == deleted_at
        assert result[1].deleted_at == deleted_at
