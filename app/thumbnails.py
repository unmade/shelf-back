from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from typing import IO, TYPE_CHECKING

import fitz
from PIL import Image, ImageSequence, UnidentifiedImageError
from PIL.ImageOps import exif_transpose

from app import errors, mediatypes

if TYPE_CHECKING:
    from PIL.Image import Image as ImageType

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
    """Return preferred quality/speed trade-off based on desired size."""
    if size >= 1920:
        return 0
    return 2


def _get_quality(size: int) -> int:
    """Return preferred image quality for compression based on desired size."""
    if size >= 1920:
        return 65
    return 80


def is_supported(mediatype: str) -> bool:
    """True if thumbnail available for a given mediatype, otherwise False."""
    return mediatype in SUPPORTED_TYPES


def thumbnail(content: IO[bytes], *, size: int) -> bytes:
    """
    Generate in-memory thumbnail with a specified sized for a given content with
    preserved aspect ratio.

    Args:
        content (IO[bytes]): File Content.
        size (int): Thumbnail size.

    Raises:
        errors.ThumbnailUnavailable: If thumbnail can't be generated for the content.

    Returns:
        bytes: Generated thumbnail as bytes.
    """
    mediatype = mediatypes.guess(name="", content=content)
    if mediatype in _SUPPORTED_PDF:
        return _thumbnail_pdf(content, size=size, mediatype=mediatype)

    # content should be strictly identified by magic numbers signature, so if no other
    # mediatype matched but some image. This is done that way because some image formats
    # are not supported by `filetype` lib.
    return _thumbnail_image(content, size=size)


def _thumbnail_image(content: IO[bytes], *, size: int) -> bytes:
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
        raise errors.ThumbnailUnavailable(msg) from exc

    buffer.seek(0)
    return buffer.read()


def _thumbnail_image_sequence(im: ImageType, size: int) -> Iterator[ImageType]:
    frames = ImageSequence.Iterator(im)
    for frame in frames:
        thumbnail = frame.copy()
        thumbnail.thumbnail((size, size))
        yield thumbnail


def _thumbnail_pdf(content: IO[bytes], *, size: int, mediatype: str) -> bytes:
    method, quality = _get_method(size), _get_quality(size)
    content.seek(0)

    with fitz.open(stream=content.read(), filetype=mediatype) as doc:
        page = doc[0]
        original_size = max(page.mediabox.height, page.mediabox.width)
        if size < original_size:
            factor = size / original_size
            matrix = fitz.Matrix(factor, factor)
        else:
            matrix = None
        pixmap = page.get_pixmap(matrix=matrix)

    buffer = BytesIO()
    pixmap.pil_save(buffer, "webp", method=method, quality=quality)
    buffer.seek(0)
    return buffer.read()
