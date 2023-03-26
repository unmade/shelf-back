from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.users.domain import Account, User
from app.app.users.services import UserService

if TYPE_CHECKING:
    from unittest.mock import MagicMock

pytestmark = [pytest.mark.asyncio]


class TestAddBookmark:
    async def test(self, user_service: UserService):
        # GIVEN
        user_id, file_id = uuid.uuid4(), uuid.uuid4()
        db = cast(mock.MagicMock, user_service.db)
        # WHEN
        await user_service.add_bookmark(user_id, file_id)
        # THEN
        db.user.add_bookmark.assert_awaited_once_with(user_id=user_id, file_id=file_id)


class TestCreate:
    @pytest.mark.parametrize(["given", "expected"], [
        (
            {
                "username": "JohnDoe",
                "password": "psswd"
            },
            {
                "user": User.construct(
                    id=mock.ANY,
                    username="johndoe",
                    password=mock.ANY,
                    superuser=False,
                ),
                "account": Account.construct(
                    id=mock.ANY,
                    username="johndoe",
                    first_name="",
                    last_name="",
                    storage_quota=None,
                    created_at=mock.ANY,
                ),
            },
        ),
        (
            {
                "username": "johndoe",
                "password": "psswd",
                "email": "johndoe@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "storage_quota": 1024,
            },
            {
                "user": User.construct(
                    id=mock.ANY,
                    username="johndoe",
                    password=mock.ANY,
                    superuser=False,
                ),
                "account": Account.construct(
                    id=mock.ANY,
                    username="johndoe",
                    email="johndoe@example.com",
                    first_name="John",
                    last_name="Doe",
                    storage_quota=1024,
                    created_at=mock.ANY,
                ),
            },
        ),
    ])
    async def test(self, user_service: UserService, given, expected):
        # GIVEN
        db = cast(mock.MagicMock, user_service.db)
        # WHEN
        with mock.patch("app.security.make_password") as make_password_mock:
            make_password_mock.return_value = "hashed_password"
            user = await user_service.create(**given)
        # THEN
        assert user == db.user.save.return_value
        make_password_mock.assert_called_once_with(given["password"])
        db.user.save.assert_awaited_once_with(expected["user"])
        db.account.save.assert_awaited_once_with(expected["account"])


class TestGetByID:
    async def test(self, user_service: UserService):
        # GIVEN
        user_id = uuid.uuid4()
        db = cast(mock.MagicMock, user_service.db)
        # WHEN
        retrieved_user = await user_service.get_by_id(user_id)
        assert retrieved_user == db.user.get_by_id.return_value
        db.user.get_by_id.assert_awaited_once_with(user_id)


class TestListBookmarks:
    async def test(self, user_service: UserService):
        # GIVEN
        user_id, file_id = uuid.uuid4(), uuid.uuid4()
        db = cast(mock.MagicMock, user_service.db)
        db.user.list_bookmarks.return_value = [file_id]
        # WHEN
        bookmarks = await user_service.list_bookmarks(user_id)
        # THEN
        assert bookmarks == db.user.list_bookmarks.return_value
        db.user.list_bookmarks.assert_awaited_once_with(user_id)


class TestRemoveBook:
    async def test(self, user_service: UserService):
        # GIVEN
        user_id, file_id = uuid.uuid4(), uuid.uuid4()
        db = cast(mock.MagicMock, user_service.db)
        # WHEN
        await user_service.remove_bookmark(user_id, file_id)
        # THEN
        db.user.remove_bookmark.assert_awaited_once_with(user_id, file_id)


@mock.patch("app.security.verify_password")
class TestVerifyCredentials:
    async def test(self, verify_password: MagicMock, user_service: UserService):
        # GIVEN
        username, password = "admin", "root"
        db = cast(mock.MagicMock, user_service.db)
        # WHEN
        user = await user_service.verify_credentials(username, password)
        # THEN
        assert user == db.user.get_by_username.return_value
        db.user.get_by_username.assert_awaited_once_with(username)
        verify_password.assert_called_once_with(password, user.password)

    async def test_when_user_does_not_exist(
        self, verify_password: MagicMock, user_service: UserService
    ):
        # GIVEN
        username, password = "admin", "root"
        db = cast(mock.MagicMock, user_service.db)
        db.user.get_by_username.side_effect = User.NotFound
        # WHEN
        user = await user_service.verify_credentials(username, password)
        # THEN
        assert user is None
        db.user.get_by_username.assert_awaited_once_with(username)
        verify_password.assert_not_called()

    async def test_when_password_is_wrong(
        self, verify_password: MagicMock, user_service: UserService
    ):
        # GIVEN
        username, password = "admin", "root"
        db = cast(mock.MagicMock, user_service.db)
        verify_password.return_value = False
        # WHEN
        user = await user_service.verify_credentials(username, password)
        # THEN
        assert user is None
        db.user.get_by_username.assert_awaited_once_with(username)
        verify_password.assert_called_once_with(
            password, db.user.get_by_username.return_value.password
        )

    async def test_case_insensitiveness(self, _: MagicMock, user_service: UserService):
        # GIVEN
        username, password = "AdMiN", "root"
        db = cast(mock.MagicMock, user_service.db)
        # WHEN
        await user_service.verify_credentials(username, password)
        # THEN
        db.user.get_by_username.assert_awaited_once_with("admin")

    async def test_stripping_spaces(self, _: MagicMock, user_service: UserService):
        # GIVEN
        username, password = " admin ", "root"
        db = cast(mock.MagicMock, user_service.db)
        # WHEN
        await user_service.verify_credentials(username, password)
        # THEN
        db.user.get_by_username.assert_awaited_once_with("admin")
