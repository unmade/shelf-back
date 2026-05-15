from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Self
from uuid import UUID

from pydantic import BaseModel

from app.toolkit import thumbnails

if TYPE_CHECKING:
    from fastapi import Request

    from app.app.files.domain import File, SharedLink


class SharedLinkSchema(BaseModel):
    file_id: UUID
    token: str
    created_at: datetime

    @classmethod
    def from_entity(cls, entity: SharedLink) -> Self:
        return cls(
            file_id=entity.file_id,
            token=entity.token,
            created_at=entity.created_at,
        )


class SharedLinkFileSchema(BaseModel):
    id: UUID
    name: str
    size: int
    modified_at: datetime
    mediatype: str
    hidden: bool = False
    thumbnail_url: str | None

    @classmethod
    def from_entity(cls, file: File, token: str, request: Request) -> Self:
        return cls(
            id=file.id,
            name=file.name,
            size=file.size,
            modified_at=file.modified_at,
            mediatype=file.mediatype,
            hidden=file.name.startswith('.'),
            thumbnail_url=cls._make_thumbnail_url(file, token, request),
        )

    @staticmethod
    def _make_thumbnail_url(file: File, token: str, request: Request) -> str | None:
        if thumbnails.is_supported(file.mediatype):
            return str(request.url_for("get_shared_link_thumbnail", token=token))
        return None


class FileIDRequest(BaseModel):
    file_id: UUID


class GetSharedLinkDownloadUrlRequest(BaseModel):
    token: str
    filename: str


class GetSharedLinkDownloadUrlResponse(BaseModel):
    download_url: str


class GetSharedLinkFileRequest(BaseModel):
    token: str
    filename: str


class ListSharedLinksResponse(BaseModel):
    items: list[SharedLinkSchema]


class RevokeSharedLinkRequest(BaseModel):
    token: str
    filename: str
