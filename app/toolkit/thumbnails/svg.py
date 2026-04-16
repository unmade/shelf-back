from __future__ import annotations

from typing import TYPE_CHECKING

from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from typing import IO

__all__ = ["thumbnail_svg"]


def thumbnail_svg(content: IO[bytes]) -> tuple[bytes, MediaType]:
    """Generates thumbnail for SVG image."""
    # SVG is a vector format, so we can just return the original content as thumbnail.
    content.seek(0)
    return content.read(), MediaType.IMAGE_SVG
