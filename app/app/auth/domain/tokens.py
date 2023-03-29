from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import Self, cast

from jose import jwt
from pydantic import BaseModel, ValidationError

from app import config
from app.toolkit import timezone

__all__ = [
    "AccessToken",
    "RefreshToken",
    "TokenError",
]

ALGORITHM = "HS256"


class TokenError(Exception):
    """Base exception class for token-related errors."""


class InvalidToken(TokenError):
    """Token is expired or can't be decoded."""


class ReusedToken(TokenError):
    """Token used more than once."""


class Encodable:
    @classmethod
    def decode(cls, token: str) -> Self:
        try:
            payload = jwt.decode(token, config.APP_SECRET_KEY, algorithms=[ALGORITHM])
            return cls(**payload)
        except (jwt.JWTError, ValidationError) as exc:
            raise InvalidToken() from exc

    def encode(self) -> str:
        return cast(
            str,
            jwt.encode(
                self.dict(),  # type: ignore[attr-defined]
                key=config.APP_SECRET_KEY,
                algorithm=ALGORITHM,
            ),
        )


class AccessToken(Encodable, BaseModel):
    sub: str
    exp: datetime

    @classmethod
    def build(cls, user_id: str) -> Self:
        return cls(
            sub=user_id,
            exp=timezone.now() + config.ACCESS_TOKEN_EXPIRE,
        )


class RefreshToken(Encodable, BaseModel):
    sub: str
    exp: datetime
    family_id: str
    token_id: str

    @classmethod
    def build(cls, user_id: str) -> Self:
        return cls(
            sub=user_id,
            exp=timezone.now() + config.REFRESH_TOKEN_EXPIRE,
            family_id=secrets.token_hex(16),
            token_id=uuid.uuid4().hex,
        )

    def rotate(self) -> Self:
        self.token_id = uuid.uuid4().hex
        return self
