from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.app.files.domain import Namespace
from app.app.users.domain import User
from app.app.users.domain.bookmark import Bookmark
from app.infrastructure.database.edgedb.db import db_context
from app.infrastructure.database.edgedb.repositories import BookmarkRepository

if TYPE_CHECKING:
    from uuid import UUID

    from ..conftest import FileFactory

pytestmark = [pytest.mark.anyio, pytest.mark.database]


async def _save_bookmark(user_id: UUID, file_id: UUID) -> Bookmark:
    query = """
        UPDATE User
        FILTER .id = <uuid>$user_id
        SET {
            bookmarks += (
                SELECT File FILTER .id = <uuid>$file_id
            )
        }"""
    conn = db_context.get()
    await conn.query_required_single(query, user_id=user_id, file_id=file_id)
    return Bookmark(user_id=user_id, file_id=file_id)


async def _list_bookmarks_id(user_id: UUID) -> list[UUID]:
    query = """SELECT User { bookmarks: { id } } FILTER .id = <uuid>$user_id"""
    user = await db_context.get().query_required_single(query, user_id=user_id)
    return [entry.id for entry in user.bookmarks]


class TestDeleteBatch:
    async def test(
        self,
        bookmark_repo: BookmarkRepository,
        file_factory: FileFactory,
        namespace_a: Namespace,
        namespace_b: Namespace,
    ):
        # GIVEN
        files_a = [await file_factory(namespace_a.path) for _ in range(3)]
        bookmarks_a = [
            await _save_bookmark(namespace_a.owner_id, file.id)
            for file in files_a
        ]
        files_b = [await file_factory(namespace_a.path) for _ in range(3)]
        bookmarks_b = [
            await _save_bookmark(namespace_b.owner_id, file.id)
            for file in files_b
        ]
        # WHEN
        await bookmark_repo.delete_batch(bookmarks_a[1:] + bookmarks_b[1:])
        # THEN
        bookmarks = await _list_bookmarks_id(namespace_a.owner_id)
        assert bookmarks == [bookmarks_a[0].file_id]
        bookmarks = await _list_bookmarks_id(namespace_b.owner_id)
        assert bookmarks == [bookmarks_b[0].file_id]


class TestListAll:
    async def test(
        self,
        bookmark_repo: BookmarkRepository,
        file_factory: FileFactory,
        namespace: Namespace,
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
        with pytest.raises(User.NotFound):
            await bookmark_repo.list_all(user_id)


class TestSaveBatch:
    async def test(
        self,
        bookmark_repo: BookmarkRepository,
        file_factory: FileFactory,
        namespace_a: Namespace,
        namespace_b: Namespace,
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
        assert set(bookmarks) == set(b.file_id for b in bookmarks_a)  # noqa: C401
        bookmarks = await _list_bookmarks_id(namespace_b.owner_id)
        assert set(bookmarks) == set(b.file_id for b in bookmarks_b)  # noqa: C401
