from __future__ import annotations

from typing import TYPE_CHECKING

from app.app.files.services.thumbnailer import thumbnails

if TYPE_CHECKING:
    from fastapi import Request

    from app.app.photos.domain import MediaItem


def make_thumbnail_url(request: Request, entity: MediaItem) -> str | None:
    if thumbnails.is_supported(entity.mediatype):
        return str(request.url_for("get_thumbnail", file_id=entity.file_id))
    return None
