from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Self, overload
from uuid import UUID

from pydantic import BaseModel, Field

from app.api.photos.utils.urls import make_thumbnail_url

if TYPE_CHECKING:
    from fastapi import Request

    from app.app.photos.domain import MediaItem
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
    slug: str
    cover: AlbumCoverSchema | None
    items_count: int
    created_at: datetime

    @classmethod
    def from_entity(cls, entity: Album, *, request: Request) -> Self:
        return cls(
            id=entity.id,
            title=entity.title,
            slug=entity.slug,
            cover=AlbumCoverSchema.from_entity(entity.cover, request=request),
            items_count=entity.items_count,
            created_at=entity.created_at,
        )


class AlbumItemSchema(BaseModel):
    file_id: UUID
    name: str
    size: int
    mediatype: str
    thumbnail_url: str | None
    modified_at: datetime
    deleted_at: datetime | None

    @classmethod
    def from_entity(cls, entity: MediaItem, request: Request) -> Self:
        return cls(
            file_id=entity.file_id,
            name=entity.name,
            size=entity.size,
            mediatype=entity.mediatype,
            thumbnail_url=make_thumbnail_url(request, entity),
            modified_at=entity.modified_at,
            deleted_at=entity.deleted_at,
        )


class AddAlbumItemsRequest(BaseModel):
    file_ids: list[UUID] = Field(..., min_length=1, max_length=1_000)


class CreateAlbumRequest(BaseModel):
    title: str = Field(min_length=1, max_length=512)
