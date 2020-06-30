from datetime import datetime, timedelta
from typing import Any, Union, cast

from jose import jwt
from passlib.context import CryptContext

from app import config

ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
