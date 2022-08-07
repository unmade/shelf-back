from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, validator

from app import security


class SignUpRequest(BaseModel):
    username: Annotated[str, Field(min_length=3, max_length=31)]
    password: Annotated[str, Field(min_length=8, max_length=63)]
    confirm_password: Annotated[str, Field(min_length=8, max_length=63)]
    email: EmailStr | None = None

    @validator("username")
    def username_is_long_and_alphanumeric(cls, value: str) -> str:
        assert value.isalnum(), (
            "Username must be at least 3 characters and contain only letters and "
            "numbers"
        )
        return value.lower()

    @validator("password")
    def password_is_strong(cls, value: str) -> str:
        assert security.is_strong_password(value), (
            "Password must be at least 8 characters including a lowercase letter, "
            "an uppercase letter, and a number"
        )
        return value

    @validator("confirm_password")
    def passwords_should_match(cls, value: str, values, **kwargs) -> str:
        if "password" in values and value != values["password"]:
            raise ValueError("Passwords do not match")
        return value


class Tokens(BaseModel):
    access_token: str
