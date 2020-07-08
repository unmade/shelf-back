from __future__ import annotations

from pydantic import BaseModel

from .namespace import Namespace


class Account(BaseModel):
    id: int
    username: str
    namespace: Namespace
