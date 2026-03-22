from __future__ import annotations

from typing import TYPE_CHECKING

from app.app.users.domain import Bookmark
from app.app.users.repositories import IBookmarkRepository
from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from collections.abc import Iterable
    from uuid import UUID

__all__ = ["BookmarkRepository"]


class BookmarkRepository(IBookmarkRepository):
    async def delete_batch(self, user_id: UUID, file_ids: Iterable[UUID]) -> None:
        await models.Bookmark.filter(
            user_id=user_id, file_id__in=list(file_ids)
        ).delete()

    async def list_all(self, user_id: UUID) -> list[Bookmark]:
        qs: list[UUID] = await (  # type: ignore[assignment]
            models.Bookmark.filter(user_id=user_id)
            .order_by("id")
            .values_list("file_id", flat=True)
        )
        return [Bookmark(user_id=user_id, file_id=file_id) for file_id in qs]

    async def save_batch(self, bookmarks: Iterable[Bookmark]) -> list[Bookmark]:
        entries = list(bookmarks)
        await models.Bookmark.bulk_create(
            [models.Bookmark(user_id=b.user_id, file_id=b.file_id) for b in entries],
            ignore_conflicts=True,
        )
        return entries
