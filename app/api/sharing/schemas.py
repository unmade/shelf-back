from __future__ import annotations

from typing import TYPE_CHECKING, Self

from pydantic import BaseModel

from app import thumbnails

if TYPE_CHECKING:
    from fastapi import Request

    from app.entities import File


class SharedLinkFile(BaseModel):
    id: str
    name: str
    size: int
    mtime: float
    mediatype: str
    hidden: bool = False
    thumbnail_url: str | None

    @classmethod
    def from_entity(
        cls, file: File, request: Request, token: str
    ) -> Self:  # type: ignore[valid-type]
        return cls.construct(
            id=file.id,
            name=file.name,
            size=file.size,
            mtime=file.mtime,
            mediatype=file.mediatype,
            hidden=file.is_hidden(),
            thumbnail_url=cls._make_thumbnail_url(request, file, token),
        )

    @staticmethod
    def _make_thumbnail_url(request: Request, file: File, token: str) -> str | None:
        if thumbnails.is_supported(file.mediatype):
            return request.url_for("get_shared_link_thumbnail", token=token)
        return None


class CreateSharedLinkResponse(BaseModel):
    token: str


class GetSharedLinkFileRequest(BaseModel):
    token: str
    filename: str
