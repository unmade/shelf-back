from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.toolkit import timezone
from app.toolkit.mediatypes import MediaType

__all__ = [
    "FilePendingDeletion",
]


class FilePendingDeletion(BaseModel):
    id: UUID
    ns_path: str
    path: str
    chash: str
    mediatype: str
    created_at: datetime = Field(default_factory=timezone.now)

    def is_folder(self) -> bool:
        """True if file is a folder, False otherwise."""
        return self.mediatype == MediaType.FOLDER
