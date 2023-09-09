from __future__ import annotations

import asyncio
from typing import IO

from app.app.files.domain import Exif, mediatypes

from .image import load_image_data

__all__ = [
    "SUPPORTED_TYPES",
    "load",
]

_SUPPORTED_IMAGES = {
    mediatypes.IMAGE_HEIC,
    mediatypes.IMAGE_HEIF,
    mediatypes.IMAGE_JPEG,
    mediatypes.IMAGE_PNG,
    mediatypes.IMAGE_WEBP,
}

SUPPORTED_TYPES = _SUPPORTED_IMAGES


async def load(content: IO[bytes]) -> Exif | None:
    """Loads metadata for a given content based on its mediatype."""
    return await asyncio.to_thread(_load, content)


def _load(content: IO[bytes]) -> Exif | None:
    mediatype = mediatypes.guess(content)
    if mediatype in _SUPPORTED_IMAGES:
        return load_image_data(content)
    return None
