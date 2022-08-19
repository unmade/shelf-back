from __future__ import annotations

from datetime import datetime
from importlib import resources
from io import BytesIO

from app import metadata
from app.entities import Exif


def test_load_metadata_for_image(image_content_with_exif: BytesIO):
    assert metadata.load(image_content_with_exif, mediatype="image/jpeg")


def test_load_metadata_but_mediatype_is_not_supported():
    assert metadata.load(BytesIO(b"Hello, world"), mediatype="plain/text") is None


def test_getexif_when_exif_is_normal() -> None:
    name = "exif_iphone_with_hdr_on.jpeg"
    with resources.open_binary("tests.data.images", name) as content:
        exif = metadata._getexif(content)

    assert exif == Exif(
        type="exif",
        make="Apple",
        model="iPhone 6",
        fnumber="2.2",
        exposure="1/40",
        iso="32",
        dt_original=datetime(2015, 4, 10, 20, 12, 23).timestamp(),
        dt_digitized=datetime(2015, 4, 10, 20, 12, 23).timestamp(),
        height=1,
        width=1,
    )


def test_getexif_when_exif_is_partial() -> None:
    name = "exif_partial.png"
    with resources.open_binary("tests.data.images", name) as content:
        exif = metadata._getexif(content)

    assert exif == Exif(
        type="exif",
        make=None,
        model=None,
        fnumber=None,
        exposure=None,
        iso=None,
        dt_original=None,
        dt_digitized=None,
        height=1,
        width=1,
    )


def test_getexif_when_there_is_no_exif(image_content: BytesIO):
    assert metadata._getexif(image_content) is None


def test_getexif_when_content_is_broken():
    content = BytesIO(b"Dummy content")
    assert metadata._getexif(content) is None
