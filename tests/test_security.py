from __future__ import annotations

import pytest

from app import security


def test_is_strong_password() -> None:
    assert security.is_strong_password("daxwif-qyrHyp-ryrca1")


@pytest.mark.parametrize("password", [
    "daxwif-",  # too short
    "qyrHyp-r",  # don't have a number
    "yp-ryrca1",  # doesn't have an uppercase letter
    "YP-RYRCA1",  # doesn't have a lowercase letter
])
def test_is_strong_password_but_its_weak(password: str):
    assert not security.is_strong_password(password)
