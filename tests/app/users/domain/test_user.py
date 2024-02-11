from __future__ import annotations

import uuid
from unittest import mock

import pytest

from app.app.users.domain import User


def _make_user(username: str, password: str) -> User:
    return User(
        id=uuid.uuid4(),
        username=username,
        password=password,
        email=None,
        email_verified=False,
        display_name="",
        active=True,
    )


class TestMakePassword:
    def test(self):
        plain_password = "plain-password"
        with mock.patch("app.toolkit.security.make_password") as make_mock:
            password = User.make_password(plain_password)

        assert password == make_mock.return_value
        make_mock.assert_called_once_with(plain_password)


class TestCheckPassword:
    def test(self):
        plain_password, hashed_password = "plain-password", "hashed-password"
        user = _make_user("admin", hashed_password)
        with mock.patch("app.toolkit.security.check_password") as check_mock:
            user.check_password(plain_password)

        check_mock.assert_called_once_with(plain_password, hashed_password)


class TestIsVerified:
    @pytest.mark.parametrize(["email_verified", "superuser", "verified"], [
        (False, False, False),
        (False, True, True),
        (True, False, True),
    ])
    def test(self, email_verified: bool, superuser: bool, verified: bool):
        # GIVEN
        user = _make_user("admin", "hashed-password")
        user.email_verified = email_verified
        user.superuser = superuser
        # WHEN
        result = user.is_verified()
        # THEN
        assert result is verified
