from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.auth.schemas import SignUpRequest


def test_sign_up_request_is_valid() -> None:
    assert SignUpRequest(
        username="user123",
        password="Password-1",
        confirm_password="Password-1",
    )


def test_sign_up_request_but_username_is_invalid() -> None:
    with pytest.raises(ValidationError) as excinfo:
        SignUpRequest(
            username="johndoe!",
            password="Password-1",
            confirm_password="Password-1"
        )

    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["loc"] == ("username", )
    assert "Username must be at least 3 characters" in errors[0]["msg"]


@pytest.mark.parametrize("password", ["password1", "Password", "!Password"])
def test_sign_up_request_but_password_is_weak(password: str):
    with pytest.raises(ValidationError) as excinfo:
        SignUpRequest(
            username="user",
            password=password,
            confirm_password=password,
        )

    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["loc"] == ("password", )
    assert "Password must be at least 8 characters" in errors[0]["msg"]


def test_sign_up_request_but_password_dont_match() -> None:
    with pytest.raises(ValidationError) as excinfo:
        SignUpRequest(
            username="user123",
            password="Password-1",
            confirm_password="Password-2",
        )

    errors = excinfo.value.errors()
    assert len(errors) == 1
    assert errors[0]["loc"] == ()
    assert errors[0]["msg"].startswith("Value error, Passwords do not match")
