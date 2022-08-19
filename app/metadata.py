from __future__ import annotations

from datetime import datetime
from fractions import Fraction
from typing import IO, TYPE_CHECKING

from PIL import ExifTags, Image, UnidentifiedImageError

from app import mediatypes
from app.entities import Exif

if TYPE_CHECKING:
    from PIL.TiffImagePlugin import IFDRational


def load(content: IO[bytes], mediatype: str) -> Exif | None:
    """
    Load metadata for a given content based on its mediatype.

    Args:
        mediatype (str): Content media type.
        content (bytes | IO[bytes]): Content to load metadata from.

    Returns:
        Exif | None: None if no metadata available, otherwise return a metadata specific
            to a given media type.
    """
    if mediatypes.is_image(mediatype):
        return _getexif(content)
    return None


def _getexif(content: IO[bytes]) -> Exif | None:
    """
    Load EXIF from an image content.

    Args:
        content (bytes | IO[bytes]): Image content.

    Returns:
        Exif | None: None if there is no EXIF in the content, otherwise Exif.
    """
    try:
        with Image.open(content) as im:
            raw_exif = im._getexif()
    except UnidentifiedImageError:
        return None

    if not raw_exif:
        return None

    exif = {
        ExifTags.TAGS[k]: v
        for k, v in raw_exif.items()
        if k in ExifTags.TAGS
    }

    return Exif(
        type="exif",
        make=exif.get("Make"),
        model=exif.get("Model"),
        fnumber=_get_str_or_none(exif.get("FNumber")),
        exposure=_get_exposure(exif.get("ExposureTime")),
        iso=_get_str_or_none(exif.get("ISOSpeedRatings")),
        dt_original=_get_timestamp(exif.get("DateTimeOriginal")),
        dt_digitized=_get_timestamp(exif.get("DateTimeDigitized")),
        height=exif.get("ExifImageHeight"),
        width=exif.get("ExifImageWidth"),
    )


def _get_str_or_none(value) -> str | None:
    if not value:
        return None
    return str(value)


def _get_timestamp(value: str | None) -> float | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y:%m:%d %H:%M:%S").timestamp()


def _get_exposure(value: IFDRational | None) -> str | None:
    if not value:
        return None
    return str(Fraction(value.numerator, value.denominator).limit_denominator(8000))
