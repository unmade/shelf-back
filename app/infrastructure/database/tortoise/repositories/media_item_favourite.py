from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from app.app.photos.repositories import IMediaItemFavouriteRepository
from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["MediaItemFavouriteRepository"]


class MediaItemFavouriteRepository(IMediaItemFavouriteRepository):
    async def add_batch(self, user_id: UUID, media_item_ids: Sequence[UUID]) -> None:
        if not media_item_ids:
            return

        await models.MediaItemBookmark.bulk_create(
            [
                models.MediaItemBookmark(user_id=user_id, media_item_id=item_id)
                for item_id in media_item_ids
            ],
            ignore_conflicts=True,
        )

    async def list_ids(self, user_id: UUID) -> list[UUID]:
        return await (  # type: ignore[return-value]
            models.MediaItemBookmark
            .filter(
                user_id=user_id,
            )
            .order_by("id")
            .values_list("media_item_id", flat=True)
        )

    async def remove_batch(self, user_id: UUID, media_item_ids: Sequence[UUID]) -> None:
        if not media_item_ids:
            return

        await models.MediaItemBookmark.filter(
            user_id=user_id,
            media_item_id__in=media_item_ids,
        ).delete()
