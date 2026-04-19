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
    media_item_id: UUID
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
            media_item_id=entity.media_item_id,
            thumbnail_url=str(
                request.url_for(
                    "get_media_item_thumbnail",
                    media_item_id=entity.media_item_id,
                )
            ),
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
    id: UUID
    name: str
    size: int
    media_type: str
    thumbnail_url: str | None
    taken_at: datetime | None
    created_at: datetime
    modified_at: datetime
    deleted_at: datetime | None

    @classmethod
    def from_entity(cls, entity: MediaItem, request: Request) -> Self:
        return cls(
            id=entity.id,
            name=entity.name,
            size=entity.size,
            media_type=entity.media_type,
            thumbnail_url=make_thumbnail_url(request, entity),
            taken_at=entity.taken_at,
            created_at=entity.created_at,
            modified_at=entity.modified_at,
            deleted_at=entity.deleted_at,
        )


class AddAlbumItemsRequest(BaseModel):
    media_item_ids: list[UUID] = Field(..., min_length=1, max_length=1_000)


class CreateAlbumRequest(BaseModel):
    title: str = Field(min_length=1, max_length=512)


class RemoveAlbumItemsRequest(BaseModel):
    media_item_ids: list[UUID] = Field(..., min_length=1, max_length=1_000)


class SetAlbumCoverRequest(BaseModel):
    media_item_id: UUID


class UpdateAlbumRequest(BaseModel):
    title: str = Field(min_length=1, max_length=512)
