from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel


class BookmarkNotFound(Exception):
    pass


class Bookmark(BaseModel):
    NotFound: ClassVar[type[Exception]] = BookmarkNotFound

    user_id: str
    file_id: str
