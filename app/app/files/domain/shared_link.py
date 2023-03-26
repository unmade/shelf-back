from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.errors import Error, ErrorCode

__all__ = ["SharedLink"]


class SharedLinkNotFound(Error):
    code = ErrorCode.shared_link_not_found


class SharedLink(BaseModel):
    NotFound = SharedLinkNotFound

    id: UUID
    file_id: str
    token: str
