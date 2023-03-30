from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

__all__ = ["SharedLink"]


class SharedLinkNotFound(Exception):
    pass


class SharedLink(BaseModel):
    NotFound = SharedLinkNotFound

    id: UUID
    file_id: str
    token: str
