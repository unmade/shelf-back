from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.users.domain import Bookmark

if TYPE_CHECKING:
    from app.app.users.services import BookmarkService

pytestmark = [pytest.mark.anyio]


class TestAddBookmark:
    async def test(self, bookmark_service: BookmarkService):
        # GIVEN
        bookmark = Bookmark(user_id=uuid.uuid4(), file_id=uuid.uuid4())
        db = cast(mock.MagicMock, bookmark_service.db)
        # WHEN
        await bookmark_service.add_bookmark(bookmark.user_id, bookmark.file_id)
        # THEN
        db.bookmark.save.assert_awaited_once_with(bookmark)


class TestListBookmarks:
    async def test(self, bookmark_service: BookmarkService):
        # GIVEN
        user_id = uuid.uuid4()
        db = cast(mock.MagicMock, bookmark_service.db)
        # WHEN
        bookmarks = await bookmark_service.list_bookmarks(user_id)
        # THEN
        assert bookmarks == db.bookmark.list_all.return_value
        db.bookmark.list_all.assert_awaited_once_with(user_id)


class TestRemoveBook:
    async def test(self, bookmark_service: BookmarkService):
        # GIVEN
        bookmark = Bookmark(user_id=uuid.uuid4(), file_id=uuid.uuid4())
        db = cast(mock.MagicMock, bookmark_service.db)
        # WHEN
        await bookmark_service.remove_bookmark(bookmark.user_id, bookmark.file_id)
        # THEN
        db.bookmark.delete.assert_awaited_once_with(bookmark)
