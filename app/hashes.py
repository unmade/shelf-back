from __future__ import annotations

from typing import IO, TYPE_CHECKING

from PIL import Image, UnidentifiedImageError

from app.app.files.domain import mediatypes

if TYPE_CHECKING:
    from collections.abc import Sequence

_SUPPORTED_IMAGES = {
    mediatypes.IMAGE_HEIC,
    mediatypes.IMAGE_HEIF,
    mediatypes.IMAGE_JPEG,
    mediatypes.IMAGE_PNG,
    mediatypes.IMAGE_WEBP,
}

SUPPORTED_TYPES = _SUPPORTED_IMAGES


class UnhashableContent(Exception):
    """Difference hash cannot be calculated for a given content."""


def dhash(content: IO[bytes], mediatype: str) -> int | None:
    """
    Calculate a difference hash based on content mediatype.

    Returns:
        int, optional: None if mediatype is unsupported, otherwise - a difference hash.
    """
    try:
        if mediatype in _SUPPORTED_IMAGES:
            return dhash_image(content)
    except UnhashableContent:
        return None
    return None


def dhash_image(content: IO[bytes], size: int = 8) -> int:
    """
    Calculate a difference hash for a greyscale image data.

    Args:
        content (IO[bytes]): Image content.
        size (int, optional): Hash size in bytes.

    Returns:
        int: A difference hash.
    """
    width, height = size + 1, size
    data = _dhash_image_prepare_data(content, width=width, height=height)

    result = 0
    for i in range(size):
        for j in range(size):
            idx = width * i + j
            result = result << 1 | (data[idx] < data[idx + 1])
    return result


def _dhash_image_prepare_data(
    content: IO[bytes],
    width: int,
    height: int,
) -> Sequence[int]:
    """
    Convert an image to greyscale and downscale.

    Args:
        content (IO[bytes]): Image content.
        width (int): Width to downscale image to.
        height (int): Height to downscale image to.

    Returns:
        Sequence[int]: Downscaled greyscale image data.
    """
    try:
        with Image.open(content) as im:
            return (  # type: ignore
                im
                .convert("L")
                .resize((width, height), Image.HAMMING)
                .getdata()
            )
    except UnidentifiedImageError as exc:
        raise UnhashableContent() from exc
