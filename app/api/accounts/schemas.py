from typing import Annotated, Optional

from pydantic import BaseModel, EmailStr, Field


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
