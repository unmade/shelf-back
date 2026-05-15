from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.toolkit import timezone

__all__ = [
    "BlobJob",
    "BlobJobDeletePayload",
    "BlobJobDeletePrefixPayload",
    "BlobJobMovePayload",
    "BlobJobMovePrefixPayload",
    "BlobJobPayload",
]


class BlobJobDeletePayload(BaseModel):
    type: Literal["delete"] = "delete"
    blob_id: UUID
    storage_key: str


class BlobJobDeletePrefixPayload(BaseModel):
    type: Literal["delete_prefix"] = "delete_prefix"
    storage_key_prefix: str


class BlobJobMovePayload(BaseModel):
    type: Literal["move"] = "move"
    blob_id: UUID
    at_storage_key: str
    to_storage_key: str


class BlobJobMovePrefixPayload(BaseModel):
    type: Literal["move_prefix"] = "move_prefix"
    at_storage_key_prefix: str
    to_storage_key_prefix: str


BlobJobPayload = Annotated[
    BlobJobDeletePayload
    | BlobJobDeletePrefixPayload
    | BlobJobMovePayload
    | BlobJobMovePrefixPayload,
    Field(discriminator="type"),
]


class BlobJob(BaseModel):
    id: UUID
    payload: BlobJobPayload
    created_at: datetime = Field(default_factory=timezone.now)
