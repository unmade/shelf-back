from __future__ import annotations

from typing import IO, TYPE_CHECKING

from PIL import Image, UnidentifiedImageError

if TYPE_CHECKING:
    pass



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
    except (Image.DecompressionBombError, UnidentifiedImageError):
        return None

    result = 0
    for i in range(size):
        for j in range(size):
            idx = width * i + j
            result = result << 1 | (data[idx] < data[idx + 1])  # type: ignore[operator]
    return result


def _dhash_image_prepare_data(
    content: IO[bytes],
    width: int,
    height: int,
) -> tuple[tuple[int, ...], ...] | tuple[float, ...]:
    """
    Converts an image to greyscale and downscale.

    Args:
        content: Image content.
        width: Width to downscale image to.
        height: Height to downscale image to.

    Returns:
        Downscaled greyscale image data.
    """
    with Image.open(content) as im:
        return (
            im
            .convert("L")
            .resize((width, height), Image.Resampling.HAMMING)
            .get_flattened_data()
        )
