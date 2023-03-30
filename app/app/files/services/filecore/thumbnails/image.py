from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from typing import IO, TYPE_CHECKING

from PIL import Image, ImageSequence, UnidentifiedImageError
from PIL.ImageOps import exif_transpose

from app.app.files.domain import File, mediatypes

if TYPE_CHECKING:
    from PIL.Image import Image as ImageType

__all__ = [
    "thumbnail_image",
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


def thumbnail_image(content: IO[bytes], *, size: int) -> bytes:
    method, quality = _get_method(size), _get_quality(size)
    buffer = BytesIO()
    try:
        with Image.open(content) as im:
            if im.format == 'GIF' and getattr(im, "is_animated", False):
                frames = _thumbnail_image_sequence(im, size)
                frame = next(frames)
                frame.info = im.info
                frame.save(buffer, "gif", save_all=True, append_images=frames)
            else:
                im.thumbnail((size, size))
                exif_transpose(im).save(buffer, "webp", method=method, quality=quality)
    except UnidentifiedImageError as exc:
        msg = "Can't generate thumbnail for a file"
        raise File.ThumbnailUnavailable(msg) from exc

    buffer.seek(0)
    return buffer.read()


def _thumbnail_image_sequence(im: ImageType, size: int) -> Iterator[ImageType]:
    frames = ImageSequence.Iterator(im)
    for frame in frames:
        thumbnail = frame.copy()
        thumbnail.thumbnail((size, size))
        yield thumbnail
