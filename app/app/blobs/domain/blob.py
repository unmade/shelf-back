from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel

__all__ = ["Blob"]


class BlobError(Exception):
    pass


class BlobNotFound(BlobError):
    pass


class Blob(BaseModel):
    Error: ClassVar[type[Exception]] = BlobError
    NotFound: ClassVar[type[BlobNotFound]] = BlobNotFound

    id: UUID
    storage_key: str
    size: int
    chash: str
    media_type: str
    created_at: datetime
