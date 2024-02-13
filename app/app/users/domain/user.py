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


class UserEmailAlreadySet(Exception):
    pass

class UserEmailAlreadyVerified(Exception):
    pass


class UserEmailIsMissing(Exception):
    pass


class UserNotFound(Exception):
    pass


class Account(BaseModel):
    StorageQuotaExceeded: ClassVar[type[StorageQuotaExceeded]] = StorageQuotaExceeded

    id: UUID
    user_id: UUID
    storage_quota: int | None = None


class User(BaseModel):
    AlreadyExists: ClassVar[type[UserAlreadyExists]] = UserAlreadyExists
    EmailAlreadyVerified: ClassVar[
        type[UserEmailAlreadyVerified]
    ] = UserEmailAlreadyVerified
    EmailIsMissing: ClassVar[type[UserEmailIsMissing]] = UserEmailIsMissing
    InvalidCredentials: ClassVar[type[InvalidCredentials]] = InvalidCredentials
    NotFound: ClassVar[type[UserNotFound]] = UserNotFound

    id: UUID
    username: str
    password: str

    email: str | None
    email_verified: bool

    display_name: str

    active: bool
    superuser: bool = False

    created_at: datetime = Field(default_factory=timezone.now)
    last_login_at: datetime | None = None

    @classmethod
    def make_password(self, plain_password: str) -> str:
        return security.make_password(plain_password)

    def check_password(self, plain_password: str) -> bool:
        return security.check_password(plain_password, self.password)

    def is_verified(self) -> bool:
        return self.superuser or self.email_verified
