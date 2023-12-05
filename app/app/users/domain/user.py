from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.toolkit import security, timezone

__all__ = [
    "Account",
    "User",
]


class InvalidCredentials(Exception):
    pass


class StorageQuotaExceeded(Exception):
    pass


class UserAlreadyExists(Exception):
    pass


class UserNotFound(Exception):
    pass


class Account(BaseModel):
    StorageQuotaExceeded: ClassVar[type[Exception]] = StorageQuotaExceeded

    id: UUID
    username: str
    email: str | None
    first_name: str
    last_name: str
    storage_quota: int | None = None
    created_at: datetime = Field(default_factory=timezone.now)


class User(BaseModel):
    AlreadyExists: ClassVar[type[Exception]] = UserAlreadyExists
    InvalidCredentials: ClassVar[type[Exception]] = InvalidCredentials
    NotFound: ClassVar[type[Exception]] = UserNotFound

    id: UUID
    username: str
    password: str
    superuser: bool = False

    @classmethod
    def make_password(self, plain_password: str) -> str:
        return security.make_password(plain_password)

    def check_password(self, plain_password: str) -> bool:
        return security.check_password(plain_password, self.password)
