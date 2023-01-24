from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app import security
from app.domain.entities import Account, User

if TYPE_CHECKING:
    from app.app.services import UserService

pytestmark = [pytest.mark.asyncio, pytest.mark.database]


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
