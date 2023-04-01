from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.files.domain import File

if TYPE_CHECKING:
    from app.app.users.usecases import UserUseCase

pytestmark = [pytest.mark.asyncio]


class TestAddBookmark:
    async def test(self, user_use_case: UserUseCase):
        # GIVEN
        user_id, file_id = uuid.uuid4(), str(uuid.uuid4())
        bookmark_service = cast(mock.MagicMock, user_use_case.bookmark_service)
        filecore = cast(mock.MagicMock, user_use_case.filecore)
        filecore.get_by_id.return_value = mock.Mock(ns_path="admin")
        ns_service = cast(mock.MagicMock, user_use_case.ns_service)
        ns_service.get_by_owner_id.return_value = mock.Mock(path="admin")
        # WHEN
        result = await user_use_case.add_bookmark(user_id, file_id)
        # THEN
        assert result == bookmark_service.add_bookmark.return_value
        filecore.get_by_id.assert_awaited_once_with(file_id)
        ns_service.get_by_owner_id.assert_awaited_once_with(user_id)
        bookmark_service.add_bookmark.assert_awaited_once_with(user_id, file_id)

    async def test_when_file_from_other_namespace(self, user_use_case: UserUseCase):
        # GIVEN
        user_id, file_id = uuid.uuid4(), str(uuid.uuid4())
        bookmark_service = cast(mock.MagicMock, user_use_case.bookmark_service)
        filecore = cast(mock.MagicMock, user_use_case.filecore)
        ns_service = cast(mock.MagicMock, user_use_case.ns_service)
        # WHEN
        with pytest.raises(File.NotFound):
            await user_use_case.add_bookmark(user_id, file_id)
        # THEN
        filecore.get_by_id.assert_awaited_once_with(file_id)
        ns_service.get_by_owner_id.assert_awaited_once_with(user_id)
        bookmark_service.add_bookmark.assert_not_awaited()


class TestListBookmark:
    async def test(self, user_use_case: UserUseCase):
        # GIVEN
        user_id = uuid.uuid4()
        bookmark_service = cast(mock.MagicMock, user_use_case.bookmark_service)
        # WHEN
        result = await user_use_case.list_bookmarks(user_id)
        # THEN
        assert result == bookmark_service.list_bookmarks.return_value
        bookmark_service.list_bookmarks.assert_awaited_once_with(user_id)


class TestRemoveBookmark:
    async def test(self, user_use_case: UserUseCase):
        # GIVEN
        user_id, file_id = uuid.uuid4(), str(uuid.uuid4())
        bookmark_service = cast(mock.MagicMock, user_use_case.bookmark_service)
        # WHEN
        await user_use_case.remove_bookmark(user_id, file_id)
        # THEN
        bookmark_service.remove_bookmark.assert_awaited_once_with(user_id, file_id)
