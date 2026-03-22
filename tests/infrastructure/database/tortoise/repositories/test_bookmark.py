from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.users.domain import User
from app.app.users.domain.bookmark import Bookmark
from app.infrastructure.database.tortoise import models

if TYPE_CHECKING:
    from uuid import UUID

    from app.infrastructure.database.tortoise.repositories import BookmarkRepository

    from ..conftest import FileFactory

pytestmark = [pytest.mark.anyio, pytest.mark.database]


async def _save_bookmark(user_id: UUID, file_id: UUID) -> Bookmark:
    await models.Bookmark.create(user_id=user_id, file_id=file_id)
    return Bookmark(user_id=user_id, file_id=file_id)


async def _list_bookmarks_id(user_id: UUID) -> list[UUID]:
    return await models.Bookmark.filter(user_id=user_id).values_list(  # type: ignore[return-value]
        "file_id", flat=True
    )


class TestDeleteBatch:
    async def test(
        self,
        bookmark_repo: BookmarkRepository,
        file_factory: FileFactory,
        namespace,
    ):
        # GIVEN
        files_a = [await file_factory(namespace.path) for _ in range(3)]
        bookmarks_a = [
            await _save_bookmark(namespace.owner_id, file.id)
            for file in files_a
        ]
        # WHEN
        await bookmark_repo.delete_batch(
            namespace.owner_id, [b.file_id for b in bookmarks_a[1:]]
        )
        # THEN
        bookmarks = await _list_bookmarks_id(namespace.owner_id)
        assert bookmarks == [bookmarks_a[0].file_id]

    async def test_when_empty(self, bookmark_repo: BookmarkRepository, user: User):
        await bookmark_repo.delete_batch(user.id, [])  # should not raise


class TestListAll:
    async def test(
        self,
        bookmark_repo: BookmarkRepository,
        file_factory: FileFactory,
        namespace,
    ):
        # GIVEN
        file_a = await file_factory(namespace.path)
        file_b = await file_factory(namespace.path)
        bookmarks = [
            await _save_bookmark(namespace.owner_id, file_a.id),
            await _save_bookmark(namespace.owner_id, file_b.id),
        ]
        # WHEN
        result = await bookmark_repo.list_all(namespace.owner_id)
        # THEN
        assert result == bookmarks

    async def test_when_no_bookmarks(
        self, bookmark_repo: BookmarkRepository, user: User
    ):
        bookmarks = await bookmark_repo.list_all(user.id)
        assert bookmarks == []

    async def test_when_user_does_not_exist(self, bookmark_repo: BookmarkRepository):
        user_id = uuid.uuid4()
        result = await bookmark_repo.list_all(user_id)
        assert result == []


class TestSaveBatch:
    async def test(
        self,
        bookmark_repo: BookmarkRepository,
        file_factory: FileFactory,
        namespace_a,
        namespace_b,
    ):
        # GIVEN
        files = [
            await file_factory(namespace_a.path),
            await file_factory(namespace_a.path),
            await file_factory(namespace_b.path),
            await file_factory(namespace_b.path),
        ]
        bookmarks_a = [
            Bookmark(user_id=namespace_a.owner_id, file_id=file.id)
            for file in files[:2]
        ]
        bookmarks_b = [
            Bookmark(user_id=namespace_b.owner_id, file_id=file.id)
            for file in files[2:]
        ]
        # WHEN
        await bookmark_repo.save_batch(bookmarks_a + bookmarks_b)
        # THEN
        bookmarks = await _list_bookmarks_id(namespace_a.owner_id)
        assert set(bookmarks) == {b.file_id for b in bookmarks_a}
        bookmarks = await _list_bookmarks_id(namespace_b.owner_id)
        assert set(bookmarks) == {b.file_id for b in bookmarks_b}
