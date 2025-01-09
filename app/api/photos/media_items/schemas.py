from __future__ import annotations

from datetime import datetime
from typing import Annotated, ClassVar, Self, TypeAlias
from uuid import UUID

from fastapi import Request
from pydantic import BaseModel, Field

from app.api.photos.utils.urls import make_thumbnail_url
from app.app.files.domain import SharedLink
from app.app.photos.domain import MediaItem
from app.app.photos.domain.media_item import (
    MediaItemCategory,
    MediaItemCategoryName,
    MediaItemCategoryOrigin,
)


class MediaItemSchema(BaseModel):
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


class CountMediaItemsResponse(BaseModel):
    total: int
    deleted: int


class AddCategoryRequest(BaseModel):
    class _Category(BaseModel):
        name: MediaItemCategoryName
        probability: int

    Categories: ClassVar[TypeAlias] = Annotated[
        list[_Category],
        Field(min_length=1, max_length=len(MediaItemCategoryName))
    ]

    file_id: UUID
    categories: AddCategoryRequest.Categories


class DeleteMediaItemBatchRequest(BaseModel):
    file_ids: Annotated[list[UUID], Field(min_length=1, max_length=1000)]


class DeleteMediaItemImmediatelyBatchRequest(BaseModel):
    file_ids: Annotated[list[UUID], Field(min_length=1, max_length=1000)]


class GetDownloadUrlRequest(BaseModel):
    file_ids: Annotated[list[UUID], Field(min_length=2, max_length=1000)]


class GetDownloadUrlResponse(BaseModel):
    download_url: str


class ListMediaItemCategoriesResponse(BaseModel):
    file_id: UUID
    categories: list[MediaItemCategorySchema]


class RestoreMediaItemBatchRequest(BaseModel):
    file_ids: Annotated[list[UUID], Field(min_length=1, max_length=1000)]


class SetMediaItemCategoriesRequest(BaseModel):
    Categories: ClassVar[TypeAlias] = Annotated[
        list[MediaItemCategoryName],
        Field(max_length=len(MediaItemCategoryName))
    ]

    file_id: UUID
    categories: SetMediaItemCategoriesRequest.Categories
