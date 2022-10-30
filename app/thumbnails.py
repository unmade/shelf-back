from __future__ import annotations

from io import BytesIO
from typing import IO

from PIL import Image, UnidentifiedImageError
from PIL.ImageOps import exif_transpose

from app import errors, mediatypes

_SUPPORTED_IMAGES = {
    mediatypes.IMAGE_HEIC,
    mediatypes.IMAGE_HEIF,
    mediatypes.IMAGE_JPEG,
    mediatypes.IMAGE_PNG,
    mediatypes.IMAGE_WEBP,
}

SUPPORTED_TYPES = _SUPPORTED_IMAGES


def is_supported(mediatype: str) -> bool:
    """True if thumbnail available for a given mediatype, otherwise False."""
    return mediatype in SUPPORTED_TYPES


def thumbnail(content: IO[bytes], *, size: int) -> bytes:
    """
    Generate in-memory thumbnail with a specified sized for a given content with
    preserved aspect of the image.

    Args:
        content (IO[bytes]): File Content.
        size (int): Thumbnail size.

    Raises:
        errors.ThumbnailUnavailable: If thumbnail can't be generated for the content.

    Returns:
        bytes: Generated thumbnail as bytes.
    """
    if size >= 1920:
        method, quality = 0, 65
    else:
        method, quality = 2, 80

    buffer = BytesIO()
    try:
        with Image.open(content) as im:
            im.thumbnail((size, size))
            exif_transpose(im).save(buffer, "webp", method=method, quality=quality)
    except UnidentifiedImageError as exc:
        msg = "Can't generate thumbnail for a file"
        raise errors.ThumbnailUnavailable(msg) from exc

    buffer.seek(0)
    return buffer.read()
