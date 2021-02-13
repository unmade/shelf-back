from __future__ import annotations

from pathlib import Path
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, validator

from app.config import TRASH_FOLDER_NAME


class Namespace(BaseModel):
    id: UUID
    path: Path

    class Config:
        orm_mode = True


class Account(BaseModel):
    id: UUID
    username: str
    namespace: Namespace

    class Config:
        orm_mode = True


class File(BaseModel):
    id: int
    parent_id: Optional[int]
    type: str
    name: str
    path: str
    size: int
    mtime: float
    hidden: bool = None

    class Config:
        orm_mode = True

    @validator("hidden", always=True)
    def is_hidden(cls, value, values, config, field):
        return values["name"].startswith(".") or values["name"] == TRASH_FOLDER_NAME


class User(BaseModel):
    id: UUID
    username: str
    password: str

    class Config:
        orm_mode = True
