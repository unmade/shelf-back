from __future__ import annotations

from typing import IO, TYPE_CHECKING

from PIL import Image, UnidentifiedImageError

if TYPE_CHECKING:
    from collections.abc import Sequence


def dhash_image(content: IO[bytes], size: int = 8) -> int | None:
    """
    Calculates a difference hash for a greyscale image data.

    Args:
        content (IO[bytes]): Image content.
        size (int, optional): Hash size in bytes.

    Returns:
        int: A difference hash.
    """
    width, height = size + 1, size
    try:
        data = _dhash_image_prepare_data(content, width=width, height=height)
    except UnidentifiedImageError:
        return None

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
    Converts an image to greyscale and downscale.

    Args:
        content (IO[bytes]): Image content.
        width (int): Width to downscale image to.
        height (int): Height to downscale image to.

    Returns:
        Sequence[int]: Downscaled greyscale image data.
    """
    with Image.open(content) as im:
        return (  # type: ignore
            im
            .convert("L")
            .resize((width, height), Image.HAMMING)
            .getdata()
        )
