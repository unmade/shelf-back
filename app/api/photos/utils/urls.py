from __future__ import annotations

from typing import TYPE_CHECKING

from app.toolkit import thumbnails

if TYPE_CHECKING:
    from fastapi import Request

    from app.app.photos.domain import MediaItem


def make_thumbnail_url(request: Request, entity: MediaItem) -> str | None:
    assert thumbnails.is_supported(entity.mediatype), (
        f"Unsupported mediatype `{entity.mediatype}` for media item `{entity.file_id}`"
    )
    return str(request.url_for("get_thumbnail", file_id=entity.file_id))
