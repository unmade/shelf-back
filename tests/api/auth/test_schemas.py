from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.auth.schemas import SignUpRequest


class TestSignUpRequest:
    def test(self) -> None:
        assert SignUpRequest(
            email="user123@example.com",
            password="Password-1",
            confirm_password="Password-1",
            display_name="John Doe",
        )

    @pytest.mark.parametrize("name", ["John", "John Doe", "Алексей", "Алексей М"])
    def test_display_name(self, name: str):
        schema = SignUpRequest(
            email="User@Example.com",
            password="Password-1",
            confirm_password="Password-1",
            display_name=name,
        )
        assert schema.display_name == name

    def test_email_is_lowercased(self) -> None:
        schema = SignUpRequest(
            email="User@Example.com",
            password="Password-1",
            confirm_password="Password-1",
            display_name="User",
        )
        assert schema.email == "user@example.com"

    def test_when_display_name_contain_forbidden_characters(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            SignUpRequest(
                email="user123@example.com",
                password="Password-1",
                confirm_password="Password-1",
                display_name="User123",
            )

        errors = excinfo.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("display_name", )
        assert "Display name can only contain" in errors[0]["msg"]

    @pytest.mark.parametrize("password", ["password1", "Password", "!Password"])
    def test_when_password_is_weak(self, password: str):
        with pytest.raises(ValidationError) as excinfo:
            SignUpRequest(
                email="user@example.com",
                password=password,
                confirm_password=password,
                display_name="user",
            )

        errors = excinfo.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("password", )
        assert "Password must be at least 8 characters" in errors[0]["msg"]

    def test_when_password_dont_match(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            SignUpRequest(
                email="user@example.com",
                password="Password-1",
                confirm_password="Password-2",
                display_name="user",
            )

        errors = excinfo.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ()
        assert errors[0]["msg"].startswith("Value error, Passwords do not match")
