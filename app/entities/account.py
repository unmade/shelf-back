from __future__ import annotations

from pydantic import BaseModel


class Account(BaseModel):
    id: int
    username: str
    namespace_id: int
