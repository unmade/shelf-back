from uuid import UUID

from pydantic import BaseModel


class IDRequest(BaseModel):
    id: UUID


class ListBookmarksResponse(BaseModel):
    items: list[str]
