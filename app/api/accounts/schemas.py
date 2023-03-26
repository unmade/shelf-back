from __future__ import annotations

from typing import TYPE_CHECKING, Self
from uuid import UUID

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.app.users.domain import Account


class AccountSchema(BaseModel):
    id: UUID
    username: str
    email: str | None
    first_name: str
    last_name: str
    superuser: bool = False

    @classmethod
    def from_entity(cls, account: Account) -> Self:
        return cls.construct(
            id=account.id,
            username=account.username,
            email=account.email,
            first_name=account.first_name,
            last_name=account.last_name,
        )


class GetAccountSpaceUsageResponse(BaseModel):
    used: int
    quota: int | None
