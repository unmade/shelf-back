from __future__ import annotations

from typing import Annotated, Optional, cast

from pydantic import BaseModel, EmailStr, Field

from app.crud.account import AccountUpdate


class Account(BaseModel):
    username: str
    email: Optional[str]
    first_name: str
    last_name: str
    superuser: bool


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
