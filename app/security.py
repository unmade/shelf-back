from __future__ import annotations

from typing import cast

from passlib.context import CryptContext

__all__ = [
    "is_strong_password",
    "make_password",
    "verify_password",
]

ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
