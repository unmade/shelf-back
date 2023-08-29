from __future__ import annotations

import uuid
from typing import cast
from unittest import mock

import pytest

from app.app.infrastructure.database import SENTINEL_ID
from app.app.users.domain import Account, User
from app.app.users.services import UserService

pytestmark = [pytest.mark.asyncio]


class TestCreate:
    @pytest.mark.parametrize(["given", "expected"], [
        (
            {
                "username": "JohnDoe",
                "password": "psswd"
            },
            {
                "user": User.model_construct(
                    id=SENTINEL_ID,
                    username="johndoe",
                    password=mock.ANY,
                    superuser=False,
                ),
                "account": Account.model_construct(
                    id=SENTINEL_ID,
                    username="johndoe",
                    email=None,
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
                "user": User.model_construct(
                    id=SENTINEL_ID,
                    username="johndoe",
                    password=mock.ANY,
                    superuser=False,
                ),
                "account": Account.model_construct(
                    id=SENTINEL_ID,
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
        with mock.patch("app.toolkit.security.make_password") as make_password_mock:
            make_password_mock.return_value = "hashed_password"
            user = await user_service.create(**given)
        # THEN
        assert user == db.user.save.return_value
        make_password_mock.assert_called_once_with(given["password"])
        db.user.save.assert_awaited_once_with(expected["user"])
        db.account.save.assert_awaited_once_with(expected["account"])


class TestGetAccount:
    async def test(self, user_service: UserService):
        # GIVEN
        user_id = uuid.uuid4()
        db = cast(mock.MagicMock, user_service.db)
        # WHEN
        account = await user_service.get_account(user_id)
        # THEN
        assert account == db.account.get_by_user_id.return_value
        db.account.get_by_user_id.assert_awaited_once_with(user_id)


class TestGetByID:
    async def test(self, user_service: UserService):
        # GIVEN
        user_id = uuid.uuid4()
        db = cast(mock.MagicMock, user_service.db)
        # WHEN
        retrieved_user = await user_service.get_by_id(user_id)
        # THEN
        assert retrieved_user == db.user.get_by_id.return_value
        db.user.get_by_id.assert_awaited_once_with(user_id)


class TestGetByUsername:
    async def test(self, user_service: UserService):
        # GIVEN
        username = "admin"
        db = cast(mock.MagicMock, user_service.db)
        # WHEN
        retrieved_user = await user_service.get_by_username(username)
        # THEN
        assert retrieved_user == db.user.get_by_username.return_value
        db.user.get_by_username.assert_awaited_once_with(username)

    async def test_case_insensitiveness(self, user_service: UserService):
        # GIVEN
        username = "AdMiN"
        db = cast(mock.MagicMock, user_service.db)
        # WHEN
        await user_service.get_by_username(username)
        # THEN
        db.user.get_by_username.assert_awaited_once_with("admin")

    async def test_stripping_spaces(self, user_service: UserService):
        # GIVEN
        username = " admin "
        db = cast(mock.MagicMock, user_service.db)
        # WHEN
        await user_service.get_by_username(username)
        # THEN
        db.user.get_by_username.assert_awaited_once_with("admin")
