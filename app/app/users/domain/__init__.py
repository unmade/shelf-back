import uuid

from .user import Account, User

__all__ = [
    "SENTINEL_ID",
    "Account",
    "User",
]

SENTINEL_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")
