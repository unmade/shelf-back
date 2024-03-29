from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.users.usecases.user import EmailUpdateLimitReached

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.users.usecases import UserUseCase

pytestmark = [pytest.mark.anyio]


class TestAddBookmarkBatch:
    async def test(self, user_use_case: UserUseCase):
        # GIVEN
        user_id = uuid.uuid4()
        file_ids = [uuid.uuid4() for _ in range(3)]
        bookmark_service = cast(mock.MagicMock, user_use_case.bookmark_service)
        ns_service = cast(mock.MagicMock, user_use_case.ns_service)
        file_service = cast(mock.MagicMock, user_use_case.file_service)
        # WHEN
        await user_use_case.add_bookmark_batch(user_id, file_ids)
        # THEN
        ns_service.get_by_owner_id.assert_awaited_once_with(user_id)
        namespace = ns_service.get_by_owner_id.return_value
        file_service.get_by_id_batch.assert_awaited_once_with(namespace.path, file_ids)
        files = file_service.get_by_id_batch.return_value
        bookmark_service.add_batch.assert_awaited_once_with(
            user_id, file_ids=[file.id for file in files]
        )


class TestChangeEmailComplete:
    @mock.patch("app.app.users.usecases.user.cache", autospec=True)
    async def test(self, cache_mock: MagicMock, user_use_case: UserUseCase):
        # GIVEN
        user_id, code = uuid.uuid4(), "078243"
        user_service = cast(mock.MagicMock, user_use_case.user_service)
        # WHEN
        await user_use_case.change_email_complete(user_id, code)
        # THEN
        user_service.change_email_complete.assert_awaited_once_with(user_id, code)
        cache_mock.set.assert_awaited_once_with(
            f"change_email:{user_id}:completed", 1, expire="6h"
        )


class TestChangeEmailResendCode:
    async def test(self, user_use_case: UserUseCase):
        # GIVEN
        user_id = uuid.uuid4()
        user_service = cast(mock.MagicMock, user_use_case.user_service)
        # WHEN
        await user_use_case.change_email_resend_code(user_id)
        # THEN
        user_service.change_email_resend_code.assert_awaited_once_with(user_id)


class TestChangeEmailStart:
    @mock.patch("app.app.users.usecases.user.cache", autospec=True)
    async def test(self, cache_mock: MagicMock, user_use_case: UserUseCase):
        # GIVEN
        user_id, email = uuid.uuid4(), "johndoe@example.com"
        user_service = cast(mock.MagicMock, user_use_case.user_service)
        cache_mock.exists.return_value = False
        # WHEN
        await user_use_case.change_email_start(user_id, email)
        # THEN
        cache_mock.exists.assert_awaited_once_with(f"change_email:{user_id}:completed")
        user_service.change_email_start.assert_awaited_once_with(user_id, email)

    @mock.patch("app.app.users.usecases.user.cache", autospec=True)
    async def test_when_limit_reached(
        self, cache_mock: MagicMock, user_use_case: UserUseCase
    ):
        # GIVEN
        user_id, email = uuid.uuid4(), "johndoe@example.com"
        user_service = cast(mock.MagicMock, user_use_case.user_service)
        cache_mock.exists.return_value = True
        # WHEN
        with pytest.raises(EmailUpdateLimitReached):
            await user_use_case.change_email_start(user_id, email)
        # THEN
        cache_mock.exists.assert_awaited_once_with(f"change_email:{user_id}:completed")
        user_service.change_email_start.assert_not_awaited()


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
        user_service.create.assert_awaited_once_with(username, password, superuser=True)
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


class TestRemoveBookmarkBatch:
    async def test(self, user_use_case: UserUseCase):
        # GIVEN
        user_id = uuid.uuid4()
        file_ids = [uuid.uuid4() for _ in range(3)]
        bookmark_service = cast(mock.MagicMock, user_use_case.bookmark_service)
        # WHEN
        await user_use_case.remove_bookmark_batch(user_id, file_ids)
        # THEN
        bookmark_service.remove_batch.assert_awaited_once_with(
            user_id, file_ids=file_ids
        )


class TestVerifyEmailSendCode:
    async def test(self, user_use_case: UserUseCase):
        # GIVEN
        user_id = uuid.uuid4()
        user_service = cast(mock.MagicMock, user_use_case.user_service)
        # WHEN
        await user_use_case.verify_email_send_code(user_id)
        # THEN
        user_service.verify_email_send_code.assert_awaited_once_with(user_id)


class TestVerifyEmailComplete:
    async def test(self, user_use_case: UserUseCase):
        # GIVEN
        user_id, code = uuid.uuid4(), "078243"
        user_service = cast(mock.MagicMock, user_use_case.user_service)
        # WHEN
        await user_use_case.verify_email_complete(user_id, code)
        # THEN
        user_service.verify_email_complete.assert_awaited_once_with(user_id, code)
