from __future__ import annotations

from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from fastapi import Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from app.api.photos.utils.urls import make_thumbnail_url
from app.app.blobs.domain import BlobMetadata
from app.app.photos.domain import MediaItem
from app.app.photos.domain.media_item import (
    MediaItemCategory,
    MediaItemCategoryName,
    MediaItemCategoryOrigin,
)
from app.toolkit.metadata import Exif


class MediaItemSchema(BaseModel):
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


class MediaItemIDRequest(BaseModel):
    media_item_id: UUID


class CountMediaItemsResponse(BaseModel):
    total: int
    deleted: int


class AddCategoryRequestCategory(BaseModel):
    name: MediaItemCategoryName
    probability: int


class AddCategoryRequest(BaseModel):
    media_item_id: UUID
    categories: Annotated[
        list[AddCategoryRequestCategory],
        Field(min_length=1, max_length=len(MediaItemCategoryName))
    ]


class DeleteMediaItemBatchRequest(BaseModel):
    ids: Annotated[list[UUID], Field(min_length=1, max_length=1000)]


class DeleteMediaItemImmediatelyBatchRequest(BaseModel):
    ids: Annotated[list[UUID], Field(min_length=1, max_length=1000)]


class GetContentMetadataResponse(BaseModel):
    media_item_id: UUID
    data: Exif

    @classmethod
    def from_entity(cls, media_item_id: UUID, entity: BlobMetadata) -> Self:
        return cls(
            media_item_id=media_item_id,
            data=entity.data,
        )


class GetDownloadUrlRequest(BaseModel):
    model_config = ConfigDict(validate_by_name=True)

    ids: Annotated[list[UUID], Field(min_length=1, max_length=1000)]


class GetDownloadUrlResponse(BaseModel):
    download_url: str


class AddFavouriteBatchRequest(BaseModel):
    ids: Annotated[list[UUID], Field(min_length=1, max_length=1000)]


class ListFavouriteMediaItemsResponse(BaseModel):
    ids: list[UUID]


class ListMediaItemCategoriesResponse(BaseModel):
    media_item_id: UUID
    categories: list[MediaItemCategorySchema]


class RestoreMediaItemBatchRequest(BaseModel):
    ids: Annotated[list[UUID], Field(min_length=1, max_length=1000)]


class RemoveFavouriteBatchRequest(BaseModel):
    ids: Annotated[list[UUID], Field(min_length=1, max_length=1000)]


class SetMediaItemCategoriesRequest(BaseModel):
    media_item_id: UUID
    categories: Annotated[
        list[MediaItemCategoryName],
        Field(max_length=len(MediaItemCategoryName))
    ]


class UploadContent(UploadFile):
    size: int
