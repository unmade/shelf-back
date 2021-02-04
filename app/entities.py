from __future__ import annotations

from pydantic import BaseModel


class Namespace(BaseModel):
    id: int
    path: str
    owner_id: int


class Account(BaseModel):
    id: int
    username: str
    namespace: Namespace
