from __future__ import annotations

from typing import TYPE_CHECKING

from app.toolkit import thumbnails

if TYPE_CHECKING:
    from fastapi import Request

    from app.app.photos.domain import MediaItem


def make_thumbnail_url(request: Request, entity: MediaItem) -> str | None:
    assert thumbnails.is_supported(entity.media_type), (
        f"Unsupported mediatype `{entity.media_type}` for media item `{entity.id}`"
    )
    return str(
        request.url_for("get_media_item_thumbnail", media_item_id=entity.id)
    )
