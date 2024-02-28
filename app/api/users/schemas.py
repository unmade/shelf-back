from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field


class AddBookmarkBatchRequest(BaseModel):
    file_ids: Annotated[set[UUID], Field(max_length=1000)]


class IDRequest(BaseModel):
    id: UUID


class ListBookmarksResponse(BaseModel):
    items: list[UUID]


class RemoveBookmarkBatchRequest(BaseModel):
    file_ids: Annotated[set[UUID], Field(max_length=1000)]
