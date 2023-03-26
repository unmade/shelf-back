from __future__ import annotations

from typing import Literal

import orjson
from pydantic import BaseModel

from app.errors import Error, ErrorCode

__all__ = [
    "ContentMetadata",
    "Exif"
]


def orjson_dumps(value, *, default=None) -> str:
    # orjson.dumps returns bytes, to match standard json.dumps we need to decode
    return orjson.dumps(value, default=default).decode()


class ContentMetadataNotFound(Error):
    code = ErrorCode.file_metadata_not_found


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
        json_loads = orjson.loads
        json_dumps = orjson_dumps


class ContentMetadata(BaseModel):
    NotFound = ContentMetadataNotFound

    file_id: str
    data: Exif
