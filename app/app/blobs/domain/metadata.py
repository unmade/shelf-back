from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel

from app.toolkit.metadata import Exif

__all__ = ["BlobMetadata"]


class BlobMetadataNotFound(Exception):
    pass


class BlobMetadata(BaseModel):
    NotFound: ClassVar[type[Exception]] = BlobMetadataNotFound

    blob_id: UUID
    data: Exif
