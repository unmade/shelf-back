from __future__ import annotations

import asyncio
from typing import IO

from app.app.files.domain import mediatypes

from .image import thumbnail_image
from .pdf import thumbnail_pdf

__all__ = [
    "SUPPORTED_TYPES",
    "is_supported",
    "thumbnail",
]

_SUPPORTED_IMAGES = {
    mediatypes.IMAGE_GIF,
    mediatypes.IMAGE_HEIC,
    mediatypes.IMAGE_HEIF,
    mediatypes.IMAGE_JPEG,
    mediatypes.IMAGE_PNG,
    mediatypes.IMAGE_WEBP,
}

_SUPPORTED_PDF = {
    "application/pdf",
    "application/epub+zip",
}

SUPPORTED_TYPES = _SUPPORTED_IMAGES | _SUPPORTED_PDF


def is_supported(mediatype: str) -> bool:
    """True if thumbnail available for a given mediatype, otherwise False."""
    return mediatype in SUPPORTED_TYPES


async def thumbnail(content: IO[bytes], *, size: int) -> bytes:
    """
    Generates in-memory thumbnail with a specified sized for a given content with
    preserved aspect ratio.

    Raises:
        File.ThumbnailUnavailable: If thumbnail can't be generated for the content.
    """
    return await asyncio.to_thread(_thumbnail, content, size)


def _thumbnail(content: IO[bytes], size: int) -> bytes:

    mediatype = mediatypes.guess(content)
    if mediatype in _SUPPORTED_PDF:
        return thumbnail_pdf(content, size=size, mediatype=mediatype)

    # content should be strictly identified by magic numbers signature, so if no other
    # mediatype matched then assume it is an image. This is done that way because some
    # image formats are not supported by `filetype` lib.
    return thumbnail_image(content, size=size)
