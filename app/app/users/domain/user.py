from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app import security, timezone

__all__ = [
    "Account",
    "User",
]


class UserAlreadyExists(Exception):
    pass


class UserNotFound(Exception):
    pass


class Account(BaseModel):
    id: UUID
    username: str
    email: str | None
    first_name: str
    last_name: str
    storage_quota: int | None
    created_at: datetime = Field(default_factory=timezone.now)


class User(BaseModel):
    AlreadyExists = UserAlreadyExists
    NotFound = UserNotFound

    id: UUID
    username: str
    password: str
    superuser: bool = False

    def check_password(self, plain_password: str) -> bool:
        return security.check_password(plain_password, self.password)
