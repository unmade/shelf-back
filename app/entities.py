from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

import orjson
from pydantic import BaseModel

from app import mediatypes

if TYPE_CHECKING:
    from app.typedefs import StrOrUUID


def orjson_dumps(value, *, default=None) -> str:
    # orjson.dumps returns bytes, to match standard json.dumps we need to decode
    return orjson.dumps(value, default=default).decode()


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
