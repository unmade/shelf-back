from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.toolkit import timezone

__all__ = ["Album"]


class AlbumCover(BaseModel):
    file_id: UUID


class Album(BaseModel):
    Cover: ClassVar[type[AlbumCover]] = AlbumCover

    id: UUID
    owner_id: UUID
    title: str
    created_at: datetime = Field(default_factory=timezone.now)
    cover: AlbumCover | None = None
