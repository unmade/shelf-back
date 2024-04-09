from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AlbumCoverSchema(BaseModel):
    file_id: UUID
    thumbnail_url: str


class AlbumSchema(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    cover: AlbumCoverSchema
