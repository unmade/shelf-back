from __future__ import annotations

from typing import cast

from passlib.context import CryptContext

__all__ = [
    "check_password",
    "make_password",
    "is_strong_password",
]

ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def check_password(plain_password: str, hashed_password: str) -> bool:
    """
    Compares a plain-text password to a hashed one.

    Args:
        plain_password (str): The plain-text password to check.
        hashed_password (str): Expected hashed password.

    Returns:
        bool: True if the password match the hash, False otherwise.
    """
    return cast(bool, pwd_context.verify(plain_password, hashed_password))


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
    Creates a hashed password.

    Args:
        password (str): Password to be hashed.

    Returns:
        str: Hashed password.
    """
    return cast(str, pwd_context.hash(password))
