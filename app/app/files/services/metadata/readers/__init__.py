from __future__ import annotations

import asyncio
from typing import IO

from app.app.files.domain import Exif, mediatypes
from app.toolkit.mediatypes import MediaType

from .image import load_image_data

__all__ = [
    "SUPPORTED_TYPES",
    "load",
]

_SUPPORTED_IMAGES = {
    MediaType.IMAGE_BMP,
    MediaType.IMAGE_HEIC,
    MediaType.IMAGE_HEIF,
    MediaType.IMAGE_JPEG,
    MediaType.IMAGE_PNG,
    MediaType.IMAGE_TIFF,
    MediaType.IMAGE_WEBP,
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
