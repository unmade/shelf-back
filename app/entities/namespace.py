from __future__ import annotations

from pydantic import BaseModel


class Namespace(BaseModel):
    id: int
    path: str
    owner_id: int
