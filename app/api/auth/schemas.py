from __future__ import annotations

import re
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
    email: EmailStr
    display_name: Annotated[str, Field(min_length=2, max_length=100)]
    password: Annotated[str, Field(min_length=8, max_length=63)]
    confirm_password: Annotated[str, Field(min_length=8, max_length=63)]

    @field_validator("email")
    @classmethod
    def lower_case_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        pattern = r'^[A-Za-z\-\'\s]+$'
        assert re.match(pattern, value), (
            "Display name can only contain letters, spaces, hyphens, and apostrophes."
        )
        return value.strip()

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
