from __future__ import annotations

from pathlib import Path
from typing import Optional, Type
from uuid import UUID

from pydantic import BaseModel

from app import mediatypes


class Account(BaseModel):
    id: UUID
    username: str
    email: Optional[str]
    first_name: str
    last_name: str

    @classmethod
    def from_db(cls: Type[Account], obj) -> Account:
        return cls.construct(
            id=obj.id,
            username=obj.user.username,
            email=obj.email,
            first_name=obj.first_name,
            last_name=obj.last_name,
        )


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
    mediatype: str

    @classmethod
    def from_db(cls: Type[File], obj) -> File:
        return cls.construct(
            id=obj.id,
            name=obj.name,
            path=obj.path,
            size=obj.size,
            mtime=obj.mtime,
            mediatype=obj.mediatype.name,
        )

    def is_folder(self) -> bool:
        """True if file is a folder, otherwise False"""
        return self.mediatype == mediatypes.FOLDER

    def is_hidden(self) -> bool:
        """True if file name startswith '.', othewise False"""
        return self.name.startswith(".")


class User(BaseModel):
    id: UUID
    username: str
    namespace: Namespace

    class Config:
        orm_mode = True
