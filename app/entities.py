from __future__ import annotations

from pathlib import Path
from uuid import UUID

from pydantic import BaseModel


class Namespace(BaseModel):
    id: UUID
    path: Path

    class Config:
        orm_mode = True


class File(BaseModel):
    id: UUID
    name: str
    path: str
    size: int
    mtime: float

    class Config:
        orm_mode = True


class User(BaseModel):
    id: UUID
    username: str
    password: str = None
    namespace: Namespace = None

    class Config:
        orm_mode = True
