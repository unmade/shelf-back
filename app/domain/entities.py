from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

import orjson
from pydantic import BaseModel, Field

from app import mediatypes, timezone

__all__ = [
    "SENTINEL_ID",
    "Account",
    "Folder",
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


class File(BaseModel):
    id: UUID
    ns_path: str
    name: str
    path: str
    size: int
    mtime: float = Field(default_factory=mtime_factory)
    mediatype: str

    def is_folder(self) -> bool:
        """True if file is a folder, False otherwise."""
        return self.mediatype == mediatypes.FOLDER

    def is_hidden(self) -> bool:
        """True if file name startswith '.', False othewise."""
        return self.name.startswith(".")


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

    def __init__(self, file_id: UUID, value: int):
        self.file_id = file_id
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


class Folder(BaseModel):
    id: UUID
    ns_path: str
    name: str
    path: str
    size: int = 0
    mtime: float = Field(default_factory=mtime_factory)
    mediatype: str = mediatypes.FOLDER

    def is_hidden(self) -> bool:
        """True if file name startswith '.', False othewise."""
        return self.name.startswith(".")


class Namespace(BaseModel):
    id: UUID
    path: str
    owner_id: UUID


class User(BaseModel):
    id: UUID
    username: str
    password: str
    superuser: bool = False
