from __future__ import annotations

from typing import TYPE_CHECKING, Self
from uuid import UUID

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.app.audit.domain.current_user_context import CurrentUser
    from app.app.users.domain import Account


class AccountUserSchema(BaseModel):
    id: UUID
    username: str


class CurrentAccountSchema(BaseModel):
    id: UUID
    username: str
    email: str | None
    first_name: str
    last_name: str
    superuser: bool = False
    user: AccountUserSchema

    @classmethod
    def from_entity(cls, account: Account, user: CurrentUser) -> Self:
        return cls(
            id=account.id,
            username=account.username,
            email=account.email,
            first_name=account.first_name,
            last_name=account.last_name,
            user=AccountUserSchema(
                id=user.id,
                username=user.username,
            )
        )


class GetAccountSpaceUsageResponse(BaseModel):
    used: int
    quota: int | None
