from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.infrastructure.database import SENTINEL_ID
from app.app.users.domain import Account, User
from app.app.users.services import UserService

if TYPE_CHECKING:
    from unittest.mock import MagicMock

pytestmark = [pytest.mark.anyio]


def _make_user(*, email: str | None, email_verified: bool = False) -> User:
    return User.model_construct(
        id=uuid.uuid4(),
        username="johndoe",
        password=mock.ANY,
        email=email,
        email_verified=email_verified,
        display_name='John Doe',
        active=True,
        created_at=mock.ANY,
        last_login_at=None,
        superuser=False,
    )


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
                    email=None,
                    email_verified=False,
                    display_name='',
                    active=True,
                    created_at=mock.ANY,
                    last_login_at=None,
                    superuser=False,
                ),
                "account": Account.model_construct(
                    id=SENTINEL_ID,
                    user_id=SENTINEL_ID,
                    storage_quota=None,
                ),
            },
        ),
        (
            {
                "username": "johndoe",
                "password": "psswd",
                "email": "johndoe@example.com",
                "display_name": "John Doe",
                "storage_quota": 1024,
            },
            {
                "user": User.model_construct(
                    id=SENTINEL_ID,
                    username="johndoe",
                    password=mock.ANY,
                    email="johndoe@example.com",
                    email_verified=False,
                    display_name="John Doe",
                    active=True,
                    created_at=mock.ANY,
                    last_login_at=None,
                    superuser=False,
                ),
                "account": Account.model_construct(
                    id=SENTINEL_ID,
                    user_id=SENTINEL_ID,
                    storage_quota=1024,
                ),
            },
        ),
    ])
    async def test(self, user_service: UserService, given, expected):
        # GIVEN
        db = cast(mock.MagicMock, user_service.db)
        db.user.save.return_value = expected["user"]
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


class TestSendEmailVerificationCode:
    async def test(self, user_service: UserService):
        # GIVEN
        user = _make_user(email="johndoe@example.com")
        db = cast(mock.MagicMock, user_service.db)
        db.user.get_by_id.return_value = user
        mail = cast(mock.MagicMock, user_service.mail)
        # WHEN
        await user_service.send_email_verification_code(user.id)
        # THEN
        db.user.get_by_id.assert_awaited_once_with(user.id)
        mail.send.assert_awaited_once()

    async def test_when_email_is_missing(self, user_service: UserService):
        # GIVEN
        user = _make_user(email=None)
        db = cast(mock.MagicMock, user_service.db)
        db.user.get_by_id.return_value = user
        mail = cast(mock.MagicMock, user_service.mail)
        # WHEN
        with pytest.raises(User.EmailIsMissing):
            await user_service.send_email_verification_code(user.id)
        # THEN
        db.user.get_by_id.assert_awaited_once_with(user.id)
        mail.send.assert_not_awaited()

    async def test_when_email_is_verified(self, user_service: UserService):
        # GIVEN
        user = _make_user(email="johndoe@example.com", email_verified=True)
        db = cast(mock.MagicMock, user_service.db)
        db.user.get_by_id.return_value = user
        mail = cast(mock.MagicMock, user_service.mail)
        # WHEN
        with pytest.raises(User.EmailAlreadyVerified):
            await user_service.send_email_verification_code(user.id)
        # THEN
        db.user.get_by_id.assert_awaited_once_with(user.id)
        mail.send.assert_not_awaited()


class TestVerifyEmail:
    @mock.patch("app.app.users.services.user.cache.get")
    async def test(self, cache_get_mock: MagicMock, user_service: UserService):
        # GIVEN
        user_id, code = uuid.uuid4(), "078243"
        cache_get_mock.return_value = code
        db = cast(mock.MagicMock, user_service.db)
        # WHEN
        result = await user_service.verify_email(user_id, code)
        # THEN
        assert result is True
        db.user.set_email_verified.assert_awaited_once_with(user_id, verified=result)

    @mock.patch("app.app.users.services.user.cache.get")
    async def test_when_code_not_set(
        self, cache_get_mock: MagicMock, user_service: UserService
    ):
        # GIVEN
        user_id, code = uuid.uuid4(), "078243"
        cache_get_mock.return_value = ""
        db = cast(mock.MagicMock, user_service.db)
        # WHEN
        result = await user_service.verify_email(user_id, code)
        # THEN
        assert result is False
        db.user.set_email_verified.assert_awaited_once_with(user_id, verified=result)

    @mock.patch("app.app.users.services.user.cache.get")
    async def test_when_code_is_invlaid(
        self, cache_get_mock: MagicMock, user_service: UserService
    ):
        # GIVEN
        user_id, code = uuid.uuid4(), "078243"
        cache_get_mock.return_value = "078244"
        db = cast(mock.MagicMock, user_service.db)
        # WHEN
        result = await user_service.verify_email(user_id, code)
        # THEN
        assert result is False
        db.user.set_email_verified.assert_awaited_once_with(user_id, verified=result)
