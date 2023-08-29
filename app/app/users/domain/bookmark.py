from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel


class BookmarkNotFound(Exception):
    pass


class Bookmark(BaseModel):
    NotFound: ClassVar[type[Exception]] = BookmarkNotFound

    user_id: UUID
    file_id: UUID
