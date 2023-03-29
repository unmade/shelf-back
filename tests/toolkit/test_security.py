from __future__ import annotations

from unittest import mock

import pytest

from app.toolkit import security


class TestCheckPassword:
    def test(self):
        plain_password, hashed_password = "root", "hashed-password"
        with mock.patch.object(security.pwd_context, "verify") as verify_mock:
            result = security.check_password(plain_password, hashed_password)
        assert result == verify_mock.return_value
        verify_mock.assert_called_once_with(plain_password, hashed_password)


class TestMakePassword:
    def test(self):
        password = "root"
        with mock.patch.object(security.pwd_context, "hash") as hasher_mock:
            result = security.make_password(password)
        assert result == hasher_mock.return_value
        hasher_mock.assert_called_once_with(password)


class TestIsStrongPassword:
    def test_strong_password(self) -> None:
        assert security.is_strong_password("daxwif-qyrHyp-ryrca1")

    @pytest.mark.parametrize("password", [
        "daxwif-",  # too short
        "qyrHyp-r",  # don't have a number
        "yp-ryrca1",  # doesn't have an uppercase letter
        "YP-RYRCA1",  # doesn't have a lowercase letter
    ])
    def test_weak_password(self, password: str):
        assert not security.is_strong_password(password)
