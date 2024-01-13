from __future__ import annotations

from datetime import datetime
from fractions import Fraction
from typing import IO, TYPE_CHECKING

from PIL import ExifTags, Image

from app.app.files.domain import Exif

if TYPE_CHECKING:
    from PIL.TiffImagePlugin import IFDRational


def load_image_data(content: IO[bytes]) -> Exif | None:
    """
    Loads EXIF from an image content.

    Args:
        content (bytes | IO[bytes]): Image content.

    Returns:
        Exif | None: None if there is no EXIF in the content, otherwise Exif.
    """
    try:
        with Image.open(content) as im:
            raw_exif = im.getexif()
            width, height = im.size
    except (Image.DecompressionBombError, Image.UnidentifiedImageError):
        return None

    if not raw_exif:
        return None

    exif = {
        ExifTags.TAGS[k]: v
        for k, v in raw_exif._get_merged_dict().items()
        if k in ExifTags.TAGS
    }

    focal_length = None
    focal_length_35mm = _get_int_or_none(exif.get("FocalLengthIn35mmFilm"))
    if not focal_length_35mm:
        focal_length = _get_int_or_none(exif.get("FocalLength"))

    return Exif(
        type="exif",
        make=_get_str_or_none(exif.get("Make")),
        model=_get_str_or_none(exif.get("Model")),
        focal_length=focal_length,
        focal_length_35mm=focal_length_35mm,
        fnumber=_get_str_or_none(exif.get("FNumber")),
        exposure=_get_exposure(exif.get("ExposureTime")),
        iso=_get_str_or_none(exif.get("ISOSpeedRatings")),
        dt_original=_get_timestamp(exif.get("DateTimeOriginal")),
        dt_digitized=_get_timestamp(exif.get("DateTimeDigitized")),
        height=width,
        width=height,
    )


def _get_int_or_none(value) -> int | None:
    if not value:
        return None
    return int(value)


def _get_str_or_none(value) -> str | None:
    if not value:
        return None
    return str(value).strip("\x00").strip()


def _get_timestamp(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip("\x00"), "%Y:%m:%d %H:%M:%S").timestamp()
    except ValueError:
        return None


def _get_exposure(value: IFDRational | None) -> str | None:
    if not value:
        return None
    return str(Fraction(value.numerator, value.denominator).limit_denominator(8000))
