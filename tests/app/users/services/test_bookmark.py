from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.users.domain import Bookmark

if TYPE_CHECKING:
    from app.app.users.services import BookmarkService

pytestmark = [pytest.mark.anyio]


class TestAddBatch:
    async def test(self, bookmark_service: BookmarkService):
        # GIVEN
        user_id = uuid.uuid4()
        file_ids = [uuid.uuid4() for _ in range(3)]
        bookmarks = [
            Bookmark(user_id=user_id, file_id=file_id)
            for file_id in file_ids
        ]
        db = cast(mock.MagicMock, bookmark_service.db)
        # WHEN
        await bookmark_service.add_batch(user_id, file_ids)
        # THEN
        db.bookmark.save_batch.assert_awaited_once_with(bookmarks)


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


class TestRemoveBatch:
    async def test(self, bookmark_service: BookmarkService):
        # GIVEN
        user_id = uuid.uuid4()
        file_ids = [uuid.uuid4() for _ in range(3)]
        bookmarks = [
            Bookmark(user_id=user_id, file_id=file_id)
            for file_id in file_ids
        ]
        db = cast(mock.MagicMock, bookmark_service.db)
        # WHEN
        await bookmark_service.remove_batch(user_id, file_ids)
        # THEN
        db.bookmark.delete_batch.assert_awaited_once_with(bookmarks)
