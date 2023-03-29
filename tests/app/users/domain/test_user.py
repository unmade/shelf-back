from __future__ import annotations

import uuid
from unittest import mock

from app.app.users.domain import User


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
        user = User(id=uuid.uuid4(), username="admin", password=hashed_password)
        with mock.patch("app.toolkit.security.check_password") as check_mock:
            user.check_password(plain_password)

        check_mock.assert_called_once_with(plain_password, hashed_password)
