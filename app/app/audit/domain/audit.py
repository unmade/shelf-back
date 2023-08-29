from __future__ import annotations

import enum
from datetime import datetime
from typing import ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.toolkit import timezone

__all__ = [
    "AuditTrail",
]


class AuditTrailAction(str, enum.Enum):
    file_added = "file_added"
    file_moved = "file_moved"
    file_trashed = "file_trashed"
    folder_created = "folder_created"
    trash_emptied = "trash_emptied"
    user_signed_in = "user_signed_in"


class AssetType(str, enum.Enum):
    file = "file"


class AuditTrailUser(BaseModel):
    id: UUID
    username: str


class AuditTrailFile(BaseModel):
    type: Literal[AssetType.file] = AssetType.file
    id: UUID
    name: str
    path: str


class AuditTrail(BaseModel):
    Action: ClassVar[type[AuditTrailAction]] = AuditTrailAction
    User: ClassVar[type[AuditTrailUser]] = AuditTrailUser
    File: ClassVar[type[AuditTrailFile]] = AuditTrailFile

    id: UUID
    action: AuditTrailAction
    user: AuditTrailUser | None
    asset: AuditTrailFile | None = None
    created_at: datetime = Field(default_factory=timezone.now)
