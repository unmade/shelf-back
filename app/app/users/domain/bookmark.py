from __future__ import annotations

from pydantic import BaseModel


class BookmarkNotFound(Exception):
    pass


class Bookmark(BaseModel):
    NotFound = BookmarkNotFound

    user_id: str
    file_id: str
