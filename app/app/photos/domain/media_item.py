from __future__ import annotations

from typing import ClassVar, Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, Field

from app.toolkit import timezone
from app.toolkit.mediatypes import MediaType

__all__ = [
    "MediaItem",
    "IMediaItemType",
]


IMediaItemType: TypeAlias = Literal[
    MediaType.IMAGE_HEIC,
    MediaType.IMAGE_HEIF,
    MediaType.IMAGE_JPEG,
    MediaType.IMAGE_PNG,
    MediaType.IMAGE_WEBP,
]


def mtime_factory() -> float:
    return timezone.now().timestamp()


class MediaItem(BaseModel):
    ALLOWED_MEDIA_TYPES: ClassVar[set[IMediaItemType]] = {
        MediaType.IMAGE_HEIC,
        MediaType.IMAGE_HEIF,
        MediaType.IMAGE_JPEG,
        MediaType.IMAGE_PNG,
        MediaType.IMAGE_WEBP,
    }

    file_id: UUID
    name: str
    size: int
    mtime: float = Field(default_factory=mtime_factory)
    mediatype: IMediaItemType
