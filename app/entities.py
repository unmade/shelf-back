from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel

from app import errors, mediatypes


class Account(BaseModel):
    id: UUID
    email: Optional[str]
    first_name: str
    last_name: str
    user: User


class File:
    __slots__ = ("id", "name", "path", "size", "mtime", "mediatype")

    def __init__(
        self,
        id: UUID,
        name: str,
        path: str,
        size: int,
        mtime: float,
        mediatype: str,
    ) -> None:
        self.id = id
        self.name = name
        self.path = path
        self.size = size
        self.mtime = mtime
        self.mediatype = mediatype

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, File):
            return NotImplemented

        return all(
            getattr(self, field) == getattr(other, field)
            for field in self.__slots__
        )

    def is_folder(self) -> bool:
        """True if file is a folder, False otherwise."""
        return self.mediatype == mediatypes.FOLDER

    def is_hidden(self) -> bool:
        """True if file name startswith '.', False othewise."""
        return self.name.startswith(".")

    def json(self) -> str:
        """Dump instance to json."""
        return json.dumps({
            "id": str(self.id),
            "name": self.name,
            "path": self.path,
            "size": self.size,
            "mtime": self.mtime,
            "mediatype": self.mediatype,
        })


class FileTaskResult:
    __slots__ = ("file", "err_code")

    def __init__(
        self,
        file: Optional[File] = None,
        err_code: Optional[errors.ErrorCode] = None,
    ) -> None:
        self.file = file
        self.err_code = err_code


class Namespace(BaseModel):
    id: UUID
    path: Path
    owner: User


class RelocationPath(BaseModel):
    from_path: str
    to_path: str


class User(BaseModel):
    id: UUID
    username: str
    superuser: bool
