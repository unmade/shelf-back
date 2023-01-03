from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

import orjson
from pydantic import BaseModel

from app import errors, mediatypes

if TYPE_CHECKING:
    from app.typedefs import StrOrUUID


def orjson_dumps(value, *, default=None) -> str:
    # orjson.dumps returns bytes, to match standard json.dumps we need to decode
    return orjson.dumps(value, default=default).decode()


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
        return orjson_dumps({
            "id": str(self.id),
            "name": self.name,
            "path": self.path,
            "size": self.size,
            "mtime": self.mtime,
            "mediatype": self.mediatype,
        })


class Exif(BaseModel):
    type: Literal["exif"] = "exif"
    make: str | None = None
    model: str | None = None
    fnumber: str | None = None
    exposure: str | None = None
    iso: str | None = None
    dt_original: float | None = None
    dt_digitized: float | None = None
    height: int | None = None
    width: int | None = None

    class Config:
        json_loads = orjson.loads
        json_dumps = orjson_dumps


class FileMetadata(BaseModel):
    file_id: str
    data: Exif


class FileTaskResult:
    __slots__ = ("file", "err_code")

    def __init__(
        self,
        file: File | None = None,
        err_code: errors.ErrorCode | None = None,
    ) -> None:
        self.file = file
        self.err_code = err_code


class Fingerprint:
    __slots__ = ("file_id", "value")

    def __init__(self, file_id: StrOrUUID, value: int):
        self.file_id = str(file_id)
        self.value = value

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Fingerprint):
            return NotImplemented

        return self.file_id == other.file_id and self.value == other.value

    def __hash__(self) -> int:
        return hash((self.file_id, self.value))

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"file_id={repr(self.file_id)}, "
            f"value={repr(self.value)}"
            ")"
        )


class RelocationPath(BaseModel):
    from_path: str
    to_path: str


class User(BaseModel):
    id: UUID
    username: str
    superuser: bool


class Namespace(BaseModel):
    id: UUID
    path: Path
    owner: User


class _SharedLinkFile(BaseModel):
    id: str
    name: str
    path: str
    mtime: float
    size: int
    mediatype: str
    namespace: Namespace


class SharedLink(BaseModel):
    File = _SharedLinkFile

    id: UUID
    token: str
    file: _SharedLinkFile
