from __future__ import annotations

from typing import Self
from uuid import UUID

from fastapi import Request
from pydantic import BaseModel

from app.app.photos.domain import MediaItem


class MediaItemSchema(BaseModel):
    file_id: UUID
    name: str
    size: int
    mtime: float
    mediatype: str
    thumbnail_url: str | None = None

    @classmethod
    def from_entity(cls, entity: MediaItem, request: Request) -> Self:
        return cls(
            file_id=entity.file_id,
            name=entity.name,
            size=entity.size,
            mtime=entity.mtime,
            mediatype=entity.mediatype,
            thumbnail_url=cls._make_thumbnail_url(request, entity),
        )

    @staticmethod
    def _make_thumbnail_url(request: Request, entity: MediaItem) -> str | None:
        return str(request.url_for("get_thumbnail", file_id=entity.file_id))