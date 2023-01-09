from __future__ import annotations

from typing import TYPE_CHECKING, Self

from pydantic import BaseModel

from app import thumbnails

if TYPE_CHECKING:
    from fastapi import Request

    from app.entities import SharedLink


class SharedLinkFileSchema(BaseModel):
    id: str
    name: str
    size: int
    mtime: float
    mediatype: str
    hidden: bool = False
    thumbnail_url: str | None

    @classmethod
    def from_entity(cls, link: SharedLink, request: Request) -> Self:
        return cls.construct(
            id=link.file.id,
            name=link.file.name,
            size=link.file.size,
            mtime=link.file.mtime,
            mediatype=link.file.mediatype,
            hidden=link.file.name.startswith('.'),
            thumbnail_url=cls._make_thumbnail_url(link, request),
        )

    @staticmethod
    def _make_thumbnail_url(link: SharedLink, request: Request, ) -> str | None:
        if thumbnails.is_supported(link.file.mediatype):
            return request.url_for("get_shared_link_thumbnail", token=link.token)
        return None


class CreateSharedLinkResponse(BaseModel):
    token: str


class GetSharedLinkResponse(BaseModel):
    token: str


class GetSharedLinkDownloadUrlRequest(BaseModel):
    token: str
    filename: str


class GetSharedLinkDownloadUrlResponse(BaseModel):
    download_url: str


class GetSharedLinkFileRequest(BaseModel):
    token: str
    filename: str


class RevokeSharedLinkRequest(BaseModel):
    token: str
    filename: str
