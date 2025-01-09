from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.contrib.slugify import slugify
from app.toolkit import timezone

__all__ = ["Album"]


class AlbumError(Exception):
    pass


class AlbumNotFound(AlbumError):
    ...


class AlbumCover(BaseModel):
    file_id: UUID


class Album(BaseModel):
    Cover: ClassVar[type[AlbumCover]] = AlbumCover

    NotFound: ClassVar[type[AlbumNotFound]] = AlbumNotFound

    id: UUID
    owner_id: UUID
    title: str
    slug: str = ""
    cover: AlbumCover | None = None
    items_count: int = 0
    created_at: datetime = Field(default_factory=timezone.now)

    @model_validator(mode="before")
    @classmethod
    def autogenerate_slug(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if 'title' in data and isinstance(data["title"], str):
                if "slug" not in data or not data["slug"]:
                    data["slug"] = slugify(data["title"], allow_unicode=True)
        return data
