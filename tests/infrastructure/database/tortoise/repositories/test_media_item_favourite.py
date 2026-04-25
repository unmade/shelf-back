from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from app.app.users.domain import User
    from app.infrastructure.database.tortoise.repositories import (
        MediaItemFavouriteRepository,
    )
    from tests.infrastructure.database.tortoise.conftest import MediaItemFactory

pytestmark = [pytest.mark.anyio, pytest.mark.database]


async def _list_favourite_ids_by_user_id(user_id: uuid.UUID) -> list[uuid.UUID]:
    return await models.MediaItemFavourite.filter(  # type: ignore[return-value]
        user_id=user_id,
    ).values_list("media_item_id", flat=True)


class TestAddBatch:
    async def test(
        self,
        media_item_favourite_repo: MediaItemFavouriteRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        items = [
            await media_item_factory(user.id),
            await media_item_factory(user.id),
        ]
        # WHEN
        await media_item_favourite_repo.add_batch(
            user.id,
            [items[0].id, items[1].id, items[0].id],
        )
        await media_item_favourite_repo.add_batch(user.id, [items[0].id])
        # THEN
        result = await _list_favourite_ids_by_user_id(user.id)
        assert set(result) == {item.id for item in items}

    async def test_when_empty(
        self,
        media_item_favourite_repo: MediaItemFavouriteRepository,
        user: User,
    ):
        await media_item_favourite_repo.add_batch(user.id, [])


class TestListIDs:
    async def test(
        self,
        media_item_favourite_repo: MediaItemFavouriteRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        items = [
            await media_item_factory(user.id),
            await media_item_factory(user.id),
        ]
        await models.MediaItemFavourite.create(
            user_id=user.id,
            media_item_id=items[0].id,
        )
        await models.MediaItemFavourite.create(
            user_id=user.id,
            media_item_id=items[1].id,
        )
        # WHEN
        result = await media_item_favourite_repo.list_ids(user.id)
        # THEN
        assert result == [items[0].id, items[1].id]

    async def test_when_empty(
        self,
        media_item_favourite_repo: MediaItemFavouriteRepository,
        user: User,
    ):
        assert await media_item_favourite_repo.list_ids(user.id) == []


class TestRemoveBatch:
    async def test(
        self,
        media_item_favourite_repo: MediaItemFavouriteRepository,
        media_item_factory: MediaItemFactory,
        user: User,
    ):
        # GIVEN
        items = [
            await media_item_factory(user.id),
            await media_item_factory(user.id),
            await media_item_factory(user.id),
        ]
        for item in items:
            await models.MediaItemFavourite.create(
                user_id=user.id,
                media_item_id=item.id,
            )
        # WHEN
        await media_item_favourite_repo.remove_batch(
            user.id,
            [items[1].id, items[2].id],
        )
        # THEN
        result = await _list_favourite_ids_by_user_id(user.id)
        assert result == [items[0].id]

    async def test_when_empty(
        self,
        media_item_favourite_repo: MediaItemFavouriteRepository,
        user: User,
    ):
        await media_item_favourite_repo.remove_batch(user.id, [])
