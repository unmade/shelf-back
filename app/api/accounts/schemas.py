from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Self
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

if TYPE_CHECKING:
    from app.app.users.domain import User


class CurrentAccountSchema(BaseModel):
    id: UUID
    username: str
    email: str | None
    display_name: str
    verified: bool
    superuser: bool = False

    @classmethod
    def from_entity(cls, user: User) -> Self:
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            verified=user.is_verified(),
            superuser=user.superuser,
        )


class ChangeEmailCompleteRequest(BaseModel):
    code: Annotated[str, Field(min_length=6)]


class ChangeEmailCompleteResponse(BaseModel):
    completed: bool


class ChangeEmailStartRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def lower_case_email(cls, value: str) -> str:
        return value.lower()


class GetAccountSpaceUsageResponse(BaseModel):
    used: int
    quota: int | None
