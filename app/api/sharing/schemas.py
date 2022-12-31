from __future__ import annotations

from pydantic import BaseModel


class CreateSharedLinkResponse(BaseModel):
    key: str
