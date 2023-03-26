from __future__ import annotations

from datetime import datetime
from uuid import UUID

import orjson
from pydantic import BaseModel, Field

from app import timezone

__all__ = [
    "SENTINEL_ID",
    "Account",
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


class User(BaseModel):
    id: UUID
    username: str
    password: str
    superuser: bool = False
