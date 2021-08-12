from __future__ import annotations

from typing import Annotated, Optional, cast
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.crud.account import AccountUpdate
from app.entities import Account as AccountEntity


class Account(BaseModel):
    id: UUID
    username: str
    email: Optional[str]
    first_name: str
    last_name: str
    superuser: bool

    @classmethod
    def from_entity(cls, account: AccountEntity) -> Account:
        return cls.construct(
            id=account.id,
            username=account.user.username,
            email=account.email,
            first_name=account.first_name,
            last_name=account.last_name,
            superuser=account.user.superuser,
        )


class CreateAccountRequest(BaseModel):
    username: Annotated[str, Field(min_length=3, max_length=31)]
    password: Annotated[str, Field(min_length=8, max_length=63)]
    email: Optional[EmailStr] = None
    first_name: Annotated[str, Field(max_length=63)] = ""
    last_name: Annotated[str, Field(max_length=63)] = ""


class UpdateAccountRequest(BaseModel):
    email: Optional[EmailStr] = None
    first_name: str = ""
    last_name: str = ""

    def as_update(self) -> AccountUpdate:
        return cast(AccountUpdate, self.dict(exclude_unset=True))
