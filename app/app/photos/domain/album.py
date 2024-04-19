from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel

__all__ = ["Album"]


class AlbumCover(BaseModel):
    file_id: UUID


class Album(BaseModel):
    Cover: ClassVar[type[AlbumCover]] = AlbumCover

    id: UUID
    owner_id: UUID
    title: str
    created_at: datetime
    cover: AlbumCover | None = None
