from __future__ import annotations

import enum
from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.toolkit import timezone

__all__ = ["MediaItem"]


class MediaItemError(Exception):
    pass


class MediaItemNotFound(MediaItemError):
    ...


class MediaItemCategoryOrigin(enum.StrEnum):
    AUTO = enum.auto()
    USER = enum.auto()


class MediaItem(BaseModel):
    NotFound: ClassVar[type[MediaItemNotFound]] = MediaItemNotFound

    id: UUID
    owner_id: UUID
    blob_id: UUID
    name: str
    media_type: str
    size: int
    chash: str
    taken_at: datetime | None = None
    created_at: datetime = Field(default_factory=timezone.now)
    modified_at: datetime = Field(default_factory=timezone.now)
    deleted_at: datetime | None = None
