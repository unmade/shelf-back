from __future__ import annotations

from pydantic import BaseModel


class Tokens(BaseModel):
    access_token: str


class TokenPayload(BaseModel):
    sub: int
