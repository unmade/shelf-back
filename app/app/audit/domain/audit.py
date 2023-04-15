from __future__ import annotations

import enum
from datetime import datetime
from typing import Literal
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
    id: str
    username: str


class AuditTrailFile(BaseModel):
    type: Literal[AssetType.file] = AssetType.file
    id: str
    name: str
    path: str


class AuditTrail(BaseModel):
    Action = AuditTrailAction
    User = AuditTrailUser
    File = AuditTrailFile

    id: UUID
    action: AuditTrailAction
    user: AuditTrailUser | None
    asset: AuditTrailFile | None
    created_at: datetime = Field(default_factory=timezone.now)
