from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

import orjson
from pydantic import BaseModel, Field

from app import mediatypes, timezone

if TYPE_CHECKING:
    from app.typedefs import StrOrUUID


__all__ = [
    "SENTINEL_ID",
    "Account",
    "Namespace",
    "User",
]

SENTINEL_ID = UUID("00000000-0000-0000-0000-000000000000")


def orjson_dumps(value, *, default=None) -> str:
    # orjson.dumps returns bytes, to match standard json.dumps we need to decode
    return orjson.dumps(value, default=default).decode()


def mtime_factory() -> float:
    return timezone.now().timestamp()


class Account(BaseModel):
    id: UUID
    username: str
    email: str | None
    first_name: str
    last_name: str
    storage_quota: int | None
    created_at: datetime = Field(default_factory=timezone.now)


class File:
    __slots__ = ("id", "ns_path", "name", "path", "size", "mtime", "mediatype")

    def __init__(
        self,
        *,
        id: StrOrUUID,
        ns_path: str,
        name: str,
        path: str,
        size: int,
        mediatype: str,
        mtime: float | None = None,
    ) -> None:
        self.id = str(id)
        self.ns_path = ns_path
        self.name = name
        self.path = path
        self.size = size
        self.mtime = mtime or mtime_factory()
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
            "ns_path": self.ns_path,
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


class ContentMetadata(BaseModel):
    file_id: str
    data: Exif


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


class Namespace(BaseModel):
    id: UUID
    path: str
    owner_id: UUID


class User(BaseModel):
    id: UUID
    username: str
    password: str
    superuser: bool = False
