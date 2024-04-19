from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Self, overload
from uuid import UUID

from pydantic import BaseModel

if TYPE_CHECKING:
    from fastapi import Request

    from app.app.photos.domain.album import Album, AlbumCover


class AlbumCoverSchema(BaseModel):
    file_id: UUID
    thumbnail_url: str

    @overload
    @classmethod
    def from_entity(cls, entity: AlbumCover, *, request: Request) -> Self: ...

    @overload
    @classmethod
    def from_entity(cls, entity: None, *, request: Request) -> None: ...

    @classmethod
    def from_entity(cls, entity: AlbumCover | None, request: Request) -> Self | None:
        if not entity:
            return None

        return cls(
            file_id=entity.file_id,
            thumbnail_url=str(request.url_for("get_thumbnail", file_id=entity.file_id))
        )


class AlbumSchema(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    cover: AlbumCoverSchema | None

    @classmethod
    def from_entity(cls, entity: Album, *, request: Request) -> Self:
        return cls(
            id=entity.id,
            title=entity.title,
            created_at=entity.created_at,
            cover=AlbumCoverSchema.from_entity(entity.cover, request=request),
        )



class CreateAlbumRequest(BaseModel):
    title: str
