from __future__ import annotations

from pathlib import Path
from typing import Type
from uuid import UUID

from pydantic import BaseModel

from app import mediatypes


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
        """True if file is a folder, False otherwise"""
        return self.mediatype == mediatypes.FOLDER


class User(BaseModel):
    id: UUID
    username: str
    namespace: Namespace

    class Config:
        orm_mode = True
