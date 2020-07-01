from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Union, cast

from jose import jwt
from passlib.context import CryptContext
from pydantic import ValidationError

from app import config

from .schemas import TokenPayload

ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class InvalidToken(Exception):
    pass


def create_access_token(
    subject: Union[str, Any], expires_delta: timedelta = None
) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    return cast(
        str,
        jwt.encode(
            {"exp": expire, "sub": str(subject)},
            config.APP_SECRET_KEY,
            algorithm=ALGORITHM,
        ),
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return cast(bool, pwd_context.verify(plain_password, hashed_password))


def get_password_hash(password: str) -> str:
    return cast(str, pwd_context.hash(password))


def check_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(token, config.APP_SECRET_KEY, algorithms=[ALGORITHM])
        return TokenPayload(**payload)
    except (jwt.JWTError, ValidationError):
        raise InvalidToken()
