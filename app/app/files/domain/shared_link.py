from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.toolkit import timezone

__all__ = ["SharedLink"]


class SharedLinkNotFound(Exception):
    pass


class SharedLink(BaseModel):
    NotFound: ClassVar[type[SharedLinkNotFound]] = SharedLinkNotFound

    id: UUID
    file_id: UUID
    token: str
    created_at: datetime = Field(default_factory=timezone.now)
