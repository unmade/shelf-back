from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel

from app.toolkit.metadata import Exif

__all__ = [
    "ContentMetadata",
]


class ContentMetadataNotFound(Exception):
    pass


class ContentMetadata(BaseModel):
    NotFound: ClassVar[type[Exception]] = ContentMetadataNotFound

    file_id: UUID
    data: Exif
