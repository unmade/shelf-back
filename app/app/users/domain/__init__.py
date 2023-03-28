import uuid

from .bookmark import Bookmark
from .user import Account, User

__all__ = [
    "SENTINEL_ID",
    "Account",
    "Bookmark",
    "User",
]

SENTINEL_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")
