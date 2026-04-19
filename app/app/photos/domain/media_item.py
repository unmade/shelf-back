from __future__ import annotations

import enum
from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.toolkit import timezone

__all__ = [
    "MediaItem",
    "MediaItemCategory",
    "MediaItemCategoryName",
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
    COOKING = enum.auto()
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
    PARTY = enum.auto()
    PEOPLE = enum.auto()
    PETS = enum.auto()
    PERFORMANCES = enum.auto()
    RECEIPTS = enum.auto()
    SCHOOL = enum.auto()
    SCREENSHOTS	 = enum.auto()
    SELFIES = enum.auto()
    SHOPPING = enum.auto()
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
    Category: ClassVar[type[MediaItemCategory]] = MediaItemCategory

    NotFound: ClassVar[type[MediaItemNotFound]] = MediaItemNotFound

    id: UUID
    owner_id: UUID
    blob_id: UUID
    name: str
    media_type: str
    size: int
    chash: str
    taken_at: datetime | None = None
    created_at: datetime = Field(default_factory=timezone.now)
    modified_at: datetime = Field(default_factory=timezone.now)
    deleted_at: datetime | None = None
