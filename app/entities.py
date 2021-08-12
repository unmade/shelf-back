from __future__ import annotations

from pathlib import Path
from typing import Optional, Type
from uuid import UUID

from pydantic import BaseModel

from app import errors, mediatypes


class Account(BaseModel):
    id: UUID
    email: Optional[str]
    first_name: str
    last_name: str
    user: User

    @classmethod
    def from_db(cls: Type[Account], obj) -> Account:
        return cls.construct(
            id=obj.id,
            email=obj.email,
            first_name=obj.first_name,
            last_name=obj.last_name,
            user=User.from_orm(obj.user),
        )


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
        """True if file is a folder, False otherwise."""
        return self.mediatype == mediatypes.FOLDER

    def is_hidden(self) -> bool:
        """True if file name startswith '.', False othewise."""
        return self.name.startswith(".")


class Namespace(BaseModel):
    id: UUID
    path: Path
    owner: User


class RelocationPath(BaseModel):
    from_path: str
    to_path: str


class RelocationResult(BaseModel):
    file: Optional[File]
    err_code: Optional[errors.ErrorCode]


class User(BaseModel):
    id: UUID
    username: str
    superuser: bool

    class Config:
        orm_mode = True
