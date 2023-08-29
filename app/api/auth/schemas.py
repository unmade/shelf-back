from __future__ import annotations

from typing import Annotated

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.toolkit import security


class SignUpRequest(BaseModel):
    username: Annotated[str, Field(min_length=3, max_length=31)]
    password: Annotated[str, Field(min_length=8, max_length=63)]
    confirm_password: Annotated[str, Field(min_length=8, max_length=63)]
    email: EmailStr | None = None

    @field_validator("username")
    @classmethod
    def username_is_long_and_alphanumeric(cls, value: str) -> str:
        assert value.isalnum(), (
            "Username must be at least 3 characters and contain only letters and "
            "numbers"
        )
        return value.lower()

    @field_validator("password")
    @classmethod
    def password_is_strong(cls, value: str) -> str:
        assert security.is_strong_password(value), (
            "Password must be at least 8 characters including a lowercase letter, "
            "an uppercase letter, and a number"
        )
        return value

    @model_validator(mode="after")
    def passwords_should_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class TokensSchema(BaseModel):
    access_token: str
    refresh_token: str
