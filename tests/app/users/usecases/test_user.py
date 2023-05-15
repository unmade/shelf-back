from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

if TYPE_CHECKING:
    from app.app.users.usecases import UserUseCase

pytestmark = [pytest.mark.asyncio]


class TestAddBookmark:
    async def test(self, user_use_case: UserUseCase):
        # GIVEN
        user_id, ns_path, file_id  = uuid.uuid4(), "admin", str(uuid.uuid4())
        bookmark_service = cast(mock.MagicMock, user_use_case.bookmark_service)
        file_service = cast(mock.MagicMock, user_use_case.file_service)
        # WHEN
        result = await user_use_case.add_bookmark(user_id, file_id, ns_path)
        # THEN
        assert result == bookmark_service.add_bookmark.return_value
        file_service.get_by_id.assert_awaited_once_with(ns_path, file_id)
        file = file_service.get_by_id.return_value
        bookmark_service.add_bookmark.assert_awaited_once_with(user_id, file.id)


class TestCreateSuperUser:
    async def test(self, user_use_case: UserUseCase):
        # GIVEN
        username, password = "admin", "password"
        ns_service = cast(mock.MagicMock, user_use_case.ns_service)
        user_service = cast(mock.MagicMock, user_use_case.user_service)
        # WHEN
        result = await user_use_case.create_superuser(username, password)
        # THEN
        assert result == user_service.create.return_value
        user_service.create.assert_awaited_once_with(username, password)
        user = user_service.create.return_value
        ns_service.create.assert_awaited_once_with(user.username, owner_id=user.id)


class TestGetAccount:
    async def test(self, user_use_case: UserUseCase):
        # GIVEN
        user_id = uuid.uuid4()
        user_service = cast(mock.MagicMock, user_use_case.user_service)
        # WHEN
        result = await user_use_case.get_account(user_id)
        # THEN
        assert result == user_service.get_account.return_value
        user_service.get_account.assert_awaited_once_with(user_id)


class TestGetAccountSpaceUsage:
    async def test(self, user_use_case: UserUseCase):
        # GIVEN
        user_id = uuid.uuid4()
        ns_service = cast(mock.MagicMock, user_use_case.ns_service)
        user_service = cast(mock.MagicMock, user_use_case.user_service)
        account = user_service.get_account.return_value
        space_used = ns_service.get_space_used_by_owner_id.return_value
        # WHEN
        result = await user_use_case.get_account_space_usage(user_id)
        # THEN
        assert result == (space_used, account.storage_quota)
        user_service.get_account.assert_awaited_once_with(user_id)
        ns_service.get_space_used_by_owner_id.assert_awaited_once_with(user_id)


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
