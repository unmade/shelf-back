from __future__ import annotations

from datetime import datetime, timedelta
from typing import cast

from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ValidationError

from app import config

__all__ = [
    "InvalidToken",
    "TokenPayload",
    "create_access_token",
    "decode_token",
    "is_strong_password",
    "make_password",
    "verify_password",
]

ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class InvalidToken(Exception):
    pass


class TokenPayload(BaseModel):
    sub: str


def create_access_token(subject: str, expires_in: timedelta = None) -> str:
    """
    Create new access token with a given subject.

    Args:
        subject (Any): Identifies the subject of the JWT.
        expires_in (timedelta, optional): The time after which the token is invalid.
            If no value is specified, then defaults to ACCESS_TOKEN_EXPIRE setting.

    Returns:
        str: Returns a JWT string.
    """
    expires_at = datetime.utcnow() + (expires_in or config.ACCESS_TOKEN_EXPIRE)

    return cast(
        str,
        jwt.encode(
            {"exp": expires_at, "sub": str(subject)},
            key=config.APP_SECRET_KEY,
            algorithm=ALGORITHM,
        ),
    )


def decode_token(token: str) -> TokenPayload:
    """
    Decode token and returns token payload.

    Args:
        token (str): Token to be decoded.

    Raises:
        InvalidToken: If there is an error decoding the token.

    Returns:
        TokenPayload: Token payload
    """
    try:
        payload = jwt.decode(token, config.APP_SECRET_KEY, algorithms=[ALGORITHM])
        return TokenPayload(**payload)
    except (jwt.JWTError, ValidationError) as exc:
        raise InvalidToken() from exc


def is_strong_password(password: str) -> bool:
    """
    Check if password is strong enough.

    Args:
        password (str): Plain-text password.

    Returns:
        bool: True if password is strong, False otherwise.
    """
    return (
        len(password) >= 8
        and any(c.isdigit() for c in password)
        and any(c.isupper() for c in password)
        and any(c.islower() for c in password)
    )


def make_password(password: str) -> str:
    """
    Create a hashed password.

    Args:
        password (str): Password to be hashed.

    Returns:
        str: Hashed password.
    """
    return cast(str, pwd_context.hash(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Compare a plain-text password to the hashed password.

    Args:
        plain_password (str): The plain-text password to check.
        hashed_password (str): Expected hashed password.

    Returns:
        bool: True if the password match the hash, False otherwise.
    """
    return cast(bool, pwd_context.verify(plain_password, hashed_password))
