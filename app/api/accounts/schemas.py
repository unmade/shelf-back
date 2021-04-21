from typing import Optional

from pydantic import BaseModel


class Account(BaseModel):
    username: str
    email: Optional[str]
    first_name: str
    last_name: str


class AccountCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    first_name: str = ""
    last_name: str = ""
