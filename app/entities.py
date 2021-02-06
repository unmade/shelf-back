from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, validator

from app.config import TRASH_FOLDER_NAME


class Namespace(BaseModel):
    id: int
    path: str
    owner_id: int


class Account(BaseModel):
    id: int
    username: str
    namespace: Namespace


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
