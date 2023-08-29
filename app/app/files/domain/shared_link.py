from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel

__all__ = ["SharedLink"]


class SharedLinkNotFound(Exception):
    pass


class SharedLink(BaseModel):
    NotFound: ClassVar[type[Exception]] = SharedLinkNotFound

    id: UUID
    file_id: UUID
    token: str
