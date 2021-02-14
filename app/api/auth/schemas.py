from __future__ import annotations

from pydantic import BaseModel

from app.entities import User


class Tokens(BaseModel):
    access_token: str


class UserMe(User):
    pass
