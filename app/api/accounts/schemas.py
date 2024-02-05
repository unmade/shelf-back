from __future__ import annotations

from typing import TYPE_CHECKING, Self
from uuid import UUID

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.app.users.domain import User


class CurrentAccountSchema(BaseModel):
    id: UUID
    username: str
    email: str | None
    email_verified: bool
    display_name: str
    superuser: bool = False

    @classmethod
    def from_entity(cls, user: User) -> Self:
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            email_verified=user.email_verified,
            display_name=user.display_name,
            superuser=user.superuser,
        )


class GetAccountSpaceUsageResponse(BaseModel):
    used: int
    quota: int | None
