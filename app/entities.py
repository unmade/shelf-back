from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

import orjson
from pydantic import BaseModel

from app import errors, mediatypes

if TYPE_CHECKING:
    from app.typedefs import StrOrUUID


class Account(BaseModel):
    id: UUID
    email: str | None
    first_name: str
    last_name: str
    user: User


class File:
    __slots__ = ("id", "name", "path", "size", "mtime", "mediatype")

    def __init__(
        self,
        id: StrOrUUID,
        name: str,
        path: str,
        size: int,
        mtime: float,
        mediatype: str,
    ) -> None:
        self.id = str(id)
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
        return orjson.dumps({
            "id": str(self.id),
            "name": self.name,
            "path": self.path,
            "size": self.size,
            "mtime": self.mtime,
            "mediatype": self.mediatype,
        }).decode()


class FileTaskResult:
    __slots__ = ("file", "err_code")

    def __init__(
        self,
        file: File | None = None,
        err_code: errors.ErrorCode | None = None,
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
