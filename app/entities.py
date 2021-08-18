from __future__ import annotations

from pathlib import Path
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app import errors, mediatypes


class Account(BaseModel):
    id: UUID
    email: Optional[str]
    first_name: str
    last_name: str
    user: User


class File(BaseModel):
    id: UUID
    name: str
    path: str
    size: int
    mtime: float
    mediatype: str

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
