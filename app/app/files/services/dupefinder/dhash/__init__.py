from __future__ import annotations

import asyncio
from typing import IO

from app.app.files.domain import mediatypes

from .image import dhash_image

__all__ = [
    "SUPPORTED_TYPES",
    "dhash",
]

_SUPPORTED_IMAGES = {
    mediatypes.IMAGE_HEIC,
    mediatypes.IMAGE_HEIF,
    mediatypes.IMAGE_JPEG,
    mediatypes.IMAGE_PNG,
    mediatypes.IMAGE_WEBP,
}

SUPPORTED_TYPES = _SUPPORTED_IMAGES


async def dhash(content: IO[bytes]) -> int | None:
    """
    Calculates a difference hash based on content mediatype.

    Args:
        content (IO[bytes]): Content to calculate difference hash for.

    Returns:
        int, optional: None if mediatype is unsupported, otherwise - a difference hash.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _dhash, content)


def _dhash(content: IO[bytes]) -> int | None:
    mediatype = mediatypes.guess(content)
    if mediatype in _SUPPORTED_IMAGES:
        return dhash_image(content)
    return None
