from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import NamedTuple, Self, cast

from jose import jwt
from pydantic import BaseModel, ValidationError

from app import config, timezone
from app.cache import cache

__all__ = [
    "InvalidToken",
    "ReusedToken",
    "AccessTokenPayload",
    "create_tokens",
    "rotate_tokens",
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


class AccessTokenPayload(Encodable, BaseModel):
    sub: str
    exp: datetime

    @classmethod
    def create(cls, subject: str) -> Self:
        return cls(
            sub=subject,
            exp=timezone.now() + config.ACCESS_TOKEN_EXPIRE,
        )


class RefreshTokenPayload(Encodable, BaseModel):
    sub: str
    exp: datetime
    family_id: str
    token_id: str

    @classmethod
    def create(cls, user_id: str) -> Self:
        return cls(
            sub=user_id,
            exp=timezone.now() + config.REFRESH_TOKEN_EXPIRE,
            family_id=secrets.token_hex(16),
            token_id=uuid.uuid4().hex,
        )

    def rotate(self) -> Self:
        self.token_id = uuid.uuid4().hex
        return self


class Tokens(NamedTuple):
    access: str
    refresh: str


async def create_tokens(user_id: str) -> Tokens:
    """
    Create a new pair of an access and refresh tokens with a given user ID as a subject.

    Args:
        user_id (str): Identifies the subject of the JWT.

    Returns:
        Tokens: Tuple of an access and refresh tokens as JWT string.
    """
    access_token_payload = AccessTokenPayload.create(user_id)
    refresh_token_payload = RefreshTokenPayload.create(user_id)

    await cache.set(
        key=refresh_token_payload.family_id,
        value=refresh_token_payload.token_id,
    )
    return Tokens(
        access=access_token_payload.encode(),
        refresh=refresh_token_payload.encode(),
    )


async def rotate_tokens(refresh_token: str) -> Tokens:
    """
    Grant a new pair of an access and refresh token based on the current refresh token.

    The refresh token will have the same `family_id` in the payload,
    but different `token_id`.

    In case given refresh token was already used, then the whole `family_id` is revoked.

    Args:
        refresh_token (str): Latest refresh token issued for the user.

    Raises:
        InvalidToken: If token is expired or can't be decoded.
        ReusedToken: If provided refresh token was already rotated.

    Returns:
        Tokens: Tuple of an access and refresh tokens as JWT strings.
    """
    refresh_token_payload = RefreshTokenPayload.decode(refresh_token)
    access_token_payload = AccessTokenPayload.create(refresh_token_payload.sub)

    token_id = await cache.get(refresh_token_payload.family_id)
    if token_id is None:
        raise InvalidToken() from None

    if token_id != refresh_token_payload.token_id:
        await cache.delete(refresh_token_payload.family_id)
        raise ReusedToken() from None

    refresh_token_payload.rotate()
    await cache.set(
        key=refresh_token_payload.family_id,
        value=refresh_token_payload.token_id,
    )
    return Tokens(
        access=access_token_payload.encode(),
        refresh=refresh_token_payload.encode(),
    )
