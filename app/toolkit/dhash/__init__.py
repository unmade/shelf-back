from __future__ import annotations

import asyncio
from typing import IO

from app.toolkit import mediatypes
from app.toolkit.mediatypes import MediaType

from .image import dhash_image

__all__ = [
    "SUPPORTED_TYPES",
    "dhash",
]

_SUPPORTED_IMAGES = {
    MediaType.IMAGE_HEIC,
    MediaType.IMAGE_HEIF,
    MediaType.IMAGE_JPEG,
    MediaType.IMAGE_PNG,
    MediaType.IMAGE_WEBP,
}

SUPPORTED_TYPES = _SUPPORTED_IMAGES


async def dhash(content: IO[bytes]) -> int | None:
    """Calculates a difference hash based on content mediatype."""
    return await asyncio.to_thread(_dhash, content)


def _dhash(content: IO[bytes]) -> int | None:
    mediatype = mediatypes.guess(content)
    if mediatype in _SUPPORTED_IMAGES:
        return dhash_image(content)
    return None
