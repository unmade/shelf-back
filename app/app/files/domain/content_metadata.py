from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.toolkit import json_

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

    class Config:
        json_loads = json_.loads
        json_dumps = json_.dumps


class ContentMetadata(BaseModel):
    NotFound = ContentMetadataNotFound

    file_id: str
    data: Exif
