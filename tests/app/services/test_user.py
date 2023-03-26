from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app import security
from app.domain.entities import Account, User

if TYPE_CHECKING:
    from app.app.files.domain import File
    from app.app.services import UserService

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


class TestAddBookmark:
    async def test(self, user: User, file: File, user_service: UserService):
        await user_service.add_bookmark(user.id, file.id)
        bookmarks = await user_service.db.user.list_bookmarks(user.id)
        assert bookmarks == [uuid.UUID(file.id)]


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
        user = await user_service.create(**given)
        assert user.id is not None
        assert user == expected["user"]
        assert security.verify_password(given["password"], user.password)


class TestGetByID:
    async def test(self, user: User, user_service: UserService):
        retrieved_user = await user_service.get_by_id(user.id)
        assert retrieved_user == user


class TestListBookmarks:
    async def test(self, user: User, file: File, user_service: UserService):
        await user_service.db.user.add_bookmark(user.id, file.id)
        bookmarks = await user_service.list_bookmarks(user.id)
        assert bookmarks == [uuid.UUID(file.id)]


class TestRemoveBook:
    async def test(self, user: User, file: File, user_service: UserService):
        await user_service.db.user.add_bookmark(user.id, file.id)
        await user_service.remove_bookmark(user.id, file.id)
        bookmarks = await user_service.list_bookmarks(user.id)
        assert bookmarks == []


class TestVerifyCredentials:
    async def test(self, user: User, user_service: UserService):
        result = await user_service.verify_credentials(user.username, "root")
        assert result == user

    async def test_when_user_does_not_exists(self, user_service: UserService):
        user = await user_service.verify_credentials("admin", "root")
        assert user is None

    async def test_when_password_is_wrong(self, user: User, user_service: UserService):
        result = await user_service.verify_credentials(user.username, "1234")
        assert result is None

    async def test_case_insensitiveness(self, user: User, user_service: UserService):
        result = await user_service.verify_credentials(user.username.upper(), "root")
        assert result == user

    async def test_stripping_spaces(self, user: User, user_service: UserService):
        result = await user_service.verify_credentials(f" {user.username} ", "root")
        assert result == user
