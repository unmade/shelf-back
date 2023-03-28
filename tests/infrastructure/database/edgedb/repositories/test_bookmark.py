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

    from app.app.files.domain import File
    from app.typedefs import StrOrUUID

    from ..conftest import FileFactory

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


async def _save_bookmark(user_id: StrOrUUID, file_id: StrOrUUID):
    query = """
        UPDATE User
        FILTER .id = <uuid>$user_id
        SET { bookmarks += (
            SELECT File FILTER .id = <uuid>$file_id
        ) }"""
    conn = db_context.get()
    await conn.query_required_single(query, user_id=user_id, file_id=file_id)


async def _list_bookmarks_id(user_id: StrOrUUID) -> list[UUID]:
    query = """SELECT User { bookmarks: { id } } FILTER .id = <uuid>$user_id"""
    user = await db_context.get().query_required_single(query, user_id=user_id)
    return [entry.id for entry in user.bookmarks]


class TestDelete:
    async def test(
        self,
        bookmark_repo: BookmarkRepository,
        file_factory: FileFactory,
        namespace: Namespace,
    ):
        # GIVEN
        user_id = namespace.owner_id
        file_a = await file_factory(namespace.path)
        file_b = await file_factory(namespace.path)
        await _save_bookmark(user_id, file_a.id)
        await _save_bookmark(user_id, file_b.id)
        bookmark = Bookmark(user_id=str(user_id), file_id=file_a.id)
        # WHEN
        await bookmark_repo.delete(bookmark)
        # THEN
        bookmarks = await _list_bookmarks_id(user_id)
        assert bookmarks == [uuid.UUID(file_b.id)]

    async def test_removing_bookmark_twice(
        self, bookmark_repo: BookmarkRepository, bookmark: Bookmark,
    ):
        # WHEN
        await bookmark_repo.delete(bookmark)
        await bookmark_repo.delete(bookmark)
        # THEN
        bookmarks = await _list_bookmarks_id(bookmark.user_id)
        assert bookmarks == []

    async def test_when_user_does_not_exist(self, bookmark_repo: BookmarkRepository):
        bookmark = Bookmark(user_id=str(uuid.uuid4()), file_id=str(uuid.uuid4()))
        with pytest.raises(User.NotFound):
            await bookmark_repo.delete(bookmark)


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
        await _save_bookmark(namespace.owner_id, file_a.id)
        await _save_bookmark(namespace.owner_id, file_b.id)
        # WHEN
        bookmarks = await bookmark_repo.list_all(namespace.owner_id)
        # THEN
        assert sorted(str(v) for v in bookmarks) == sorted([file_a.id, file_b.id])

    async def test_when_no_bookmarks(
        self, bookmark_repo: BookmarkRepository, user: User
    ):
        bookmarks = await bookmark_repo.list_all(user.id)
        assert bookmarks == []

    async def test_when_user_does_not_exist(self, bookmark_repo: BookmarkRepository):
        user_id = uuid.uuid4()
        with pytest.raises(User.NotFound):
            await bookmark_repo.list_all(user_id)


class TestSave:
    async def test(self, bookmark_repo: BookmarkRepository, user: User, file: File):
        # GIVEN
        bookmark = Bookmark(user_id=str(user.id), file_id=file.id)
        # WHEN
        await bookmark_repo.save(bookmark)
        # THEN
        bookmarks = await _list_bookmarks_id(user.id)
        assert len(bookmarks) == 1

    async def test_adding_twice(
        self, bookmark_repo: BookmarkRepository, bookmark: Bookmark
    ):
        # WHEN
        await bookmark_repo.save(bookmark)
        await bookmark_repo.save(bookmark)
        # THEN
        bookmarks = await _list_bookmarks_id(bookmark.user_id)
        assert len(bookmarks) == 1

    async def test_when_user_does_not_exist(
        self, bookmark_repo: BookmarkRepository, file: File
    ):
        bookmark = Bookmark(user_id=str(uuid.uuid4()), file_id=file.id)
        with pytest.raises(User.NotFound):
            await bookmark_repo.save(bookmark)

    async def test_when_file_does_not_exist(
        self, bookmark_repo: BookmarkRepository, user: User,
    ):
        # GIVEN
        bookmark = Bookmark(user_id=str(user.id), file_id=str(uuid.uuid4()))
        # WHEN
        await bookmark_repo.save(bookmark)
        # THEN
        bookmarks = await _list_bookmarks_id(user.id)
        assert len(bookmarks) == 0
