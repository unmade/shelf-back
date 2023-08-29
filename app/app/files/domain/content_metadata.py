from __future__ import annotations

from typing import ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel

__all__ = [
    "ContentMetadata",
    "Exif"
]


class ContentMetadataNotFound(Exception):
    pass


class Exif(BaseModel):
    type: Literal["exif"] = "exif"
    make: str | None = None
    model: str | None = None
    fnumber: str | None = None
    exposure: str | None = None
    iso: str | None = None
    dt_original: float | None = None
    dt_digitized: float | None = None
    height: int | None = None
    width: int | None = None


class ContentMetadata(BaseModel):
    NotFound: ClassVar[type[Exception]] = ContentMetadataNotFound

    file_id: UUID
    data: Exif
