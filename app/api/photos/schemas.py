from __future__ import annotations

from datetime import datetime
from typing import Annotated, ClassVar, Self, TypeAlias
from uuid import UUID

from fastapi import Request
from pydantic import BaseModel, Field

from app.app.files.domain import SharedLink
from app.app.photos.domain import MediaItem
from app.app.photos.domain.media_item import (
    MediaItemCategory,
    MediaItemCategoryName,
    MediaItemCategoryOrigin,
)


def _make_thumbnail_url(request: Request, entity: MediaItem) -> str:
    return str(request.url_for("get_thumbnail", file_id=entity.file_id))


class MediaItemSchema(BaseModel):
    file_id: UUID
    name: str
    size: int
    mtime: float
    mediatype: str
    thumbnail_url: str
    deleted_at: datetime | None

    @classmethod
    def from_entity(cls, entity: MediaItem, request: Request) -> Self:
        return cls(
            file_id=entity.file_id,
            name=entity.name,
            size=entity.size,
            mtime=entity.mtime,
            mediatype=entity.mediatype,
            thumbnail_url=_make_thumbnail_url(request, entity),
            deleted_at=entity.deleted_at,
        )


class MediaItemCategorySchema(BaseModel):
    name: MediaItemCategoryName
    origin: MediaItemCategoryOrigin
    probability: int

    @classmethod
    def from_entity(cls, entity: MediaItemCategory) -> Self:
        return cls(
            name=entity.name,
            origin=entity.origin,
            probability=entity.probability,
        )


class MediaItemSharedLinkSchema(BaseModel):
    token: str
    created_at: datetime
    item: MediaItemSchema

    @classmethod
    def from_entity(
        cls, item: MediaItem, link: SharedLink, *, request: Request
    ) -> Self:
        return cls(
            token=link.token,
            created_at=link.created_at,
            item=MediaItemSchema.from_entity(item, request),
        )


class FileIDRequest(BaseModel):
    file_id: UUID


class AddCategoryRequest(BaseModel):
    class _Category(BaseModel):
        name: MediaItemCategoryName
        probability: int

    Categories: ClassVar[TypeAlias] = Annotated[
        list[_Category],
        Field(min_length=1, max_length=len(MediaItemCategoryName))
    ]

    file_id: UUID
    categories: Categories


class DeleteMediaItemBatchRequest(BaseModel):
    file_ids: list[UUID]


class ListMediaItemCategoriesResponse(BaseModel):
    file_id: UUID
    categories: list[MediaItemCategorySchema]


class RestoreMediaItemBatchRequest(BaseModel):
    file_ids: list[UUID]


class SetMediaItemCategoriesRequest(BaseModel):
    Categories: ClassVar[TypeAlias] = Annotated[
        list[MediaItemCategoryName],
        Field(max_length=len(MediaItemCategoryName))
    ]

    file_id: UUID
    categories: Categories
