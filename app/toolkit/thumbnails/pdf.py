from __future__ import annotations

from io import BytesIO
from typing import IO

import fitz

from app.toolkit.mediatypes import MediaType

__all__ = [
    "thumbnail_pdf",
]

_SUPPORTED_IMAGES = {
    MediaType.IMAGE_GIF,
    MediaType.IMAGE_HEIC,
    MediaType.IMAGE_HEIF,
    MediaType.IMAGE_JPEG,
    MediaType.IMAGE_PNG,
    MediaType.IMAGE_WEBP,
}

_SUPPORTED_PDF = {
    MediaType.PDF,
    MediaType.EPUB,
}

SUPPORTED_TYPES = _SUPPORTED_IMAGES | _SUPPORTED_PDF


def _get_method(size: int) -> int:
    """Returns preferred quality/speed trade-off based on desired size."""
    if size >= 1920:
        return 0
    return 2


def _get_quality(size: int) -> int:
    """Returns preferred image quality for compression based on desired size."""
    if size >= 1920:
        return 65
    return 80


def thumbnail_pdf(
    content: IO[bytes], *, size: int, mediatype: str
) -> tuple[bytes, MediaType]:
    method, quality = _get_method(size), _get_quality(size)
    content.seek(0)

    with fitz.open(stream=content.read(), filetype=mediatype) as doc:
        page = doc[0]
        original_size = max(page.mediabox.height, page.mediabox.width)
        if size < original_size:
            factor = size / original_size
            matrix = fitz.Matrix(factor, factor)
        else:
            matrix = None
        pixmap = page.get_pixmap(matrix=matrix)

    buffer = BytesIO()
    pixmap.pil_save(buffer, "webp", method=method, quality=quality)
    buffer.seek(0)
    return buffer.read(), MediaType.IMAGE_WEBP
