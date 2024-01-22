from __future__ import annotations

import enum
from typing import ClassVar, Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, Field

from app.toolkit import timezone
from app.toolkit.mediatypes import MediaType

__all__ = [
    "IMediaItemType",
    "MediaItem",
    "MediaItemCategory",
    "MediaItemCategoryName",
]


def mtime_factory() -> float:
    return timezone.now().timestamp()


IMediaItemType: TypeAlias = Literal[
    MediaType.IMAGE_HEIC,
    MediaType.IMAGE_HEIF,
    MediaType.IMAGE_JPEG,
    MediaType.IMAGE_PNG,
    MediaType.IMAGE_WEBP,
]


class MediaItemError(Exception):
    pass


class MediaItemNotFound(MediaItemError):
    ...


class MediaItemCategoryName(enum.StrEnum):
    ANIMALS = enum.auto()
    ARTS = enum.auto()
    BIRTHDAYS = enum.auto()
    CITYSCAPES = enum.auto()
    CRAFTS = enum.auto()
    DOCUMENTS = enum.auto()
    FASHION = enum.auto()
    FLOWERS = enum.auto()
    FOOD = enum.auto()
    GARDENS = enum.auto()
    HOLIDAYS = enum.auto()
    HOUSES = enum.auto()
    LANDMARKS = enum.auto()
    LANDSCAPES = enum.auto()
    NIGHT = enum.auto()
    PEOPLE = enum.auto()
    PETS = enum.auto()
    PERFORMANCES = enum.auto()
    RECEIPTS = enum.auto()
    SCREENSHOTS	 = enum.auto()
    SELFIES = enum.auto()
    SPORT = enum.auto()
    TRAVEL = enum.auto()
    UTILITY = enum.auto()
    WEDDINGS = enum.auto()
    WHITEBOARDS = enum.auto()


class MediaItemCategoryOrigin(enum.StrEnum):
    AUTO = enum.auto()
    USER = enum.auto()


class MediaItemCategory(BaseModel):
    Name: ClassVar[type[MediaItemCategoryName]] = MediaItemCategoryName
    Origin: ClassVar[type[MediaItemCategoryOrigin]] = MediaItemCategoryOrigin

    name: MediaItemCategoryName
    origin: MediaItemCategoryOrigin
    probability: int


class MediaItem(BaseModel):
    ALLOWED_MEDIA_TYPES: ClassVar[set[IMediaItemType]] = {
        MediaType.IMAGE_HEIC,
        MediaType.IMAGE_HEIF,
        MediaType.IMAGE_JPEG,
        MediaType.IMAGE_PNG,
        MediaType.IMAGE_WEBP,
    }

    Category: ClassVar[type[MediaItemCategory]] = MediaItemCategory

    NotFound: ClassVar[type[MediaItemNotFound]] = MediaItemNotFound

    file_id: UUID
    name: str
    size: int
    mtime: float = Field(default_factory=mtime_factory)
    mediatype: IMediaItemType
