from __future__ import annotations

from datetime import datetime
from uuid import UUID

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


class Folder(BaseModel):
    id: UUID
    ns_path: str
    name: str
    path: str
    size: int = 0
    mtime: float = Field(default_factory=mtime_factory)
    mediatype: str = mediatypes.FOLDER


class Namespace(BaseModel):
    id: UUID
    path: str
    owner_id: UUID


class User(BaseModel):
    id: UUID
    username: str
    password: str
    superuser: bool = False
