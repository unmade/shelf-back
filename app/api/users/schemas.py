from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field


class IDRequest(BaseModel):
    id: UUID


class ListBookmarksResponse(BaseModel):
    items: list[UUID]


class VerifyEmailRequest(BaseModel):
    code: Annotated[str, Field(min_length=6)]


class VerifyEmailResponse(BaseModel):
    verified: bool
