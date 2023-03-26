from __future__ import annotations

from datetime import datetime
from importlib import resources
from io import BytesIO

import pytest

from app import metadata
from app.app.files.domain import Exif


def test_load_metadata_for_image(image_content_with_exif: BytesIO):
    assert metadata.load(image_content_with_exif, mediatype="image/jpeg")


def test_load_metadata_but_mediatype_is_not_supported():
    assert metadata.load(BytesIO(b"Hello, world"), mediatype="plain/text") is None


@pytest.mark.parametrize(["name", "expected"], [
    (
        "exif_iphone_with_hdr_on.jpeg",
        Exif(
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
        ),
    ),
    (
        "exif_iphone.heic",
        Exif(
            type="exif",
            make="Apple",
            model="iPhone 8",
            fnumber="1.8",
            exposure="1/873",
            iso="20",
            dt_original=datetime(2018, 5, 28, 20, 35, 36).timestamp(),
            dt_digitized=datetime(2018, 5, 28, 20, 35, 36).timestamp(),
            height=1,
            width=1,
        ),
    ),
    (
        "exif_partial.png",
        Exif(
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
        ),
    ),
    (
        "exif_nullterminated.jpg",
        Exif(
            type="exif",
            make="Phase One A/S",
            model="IQ3 100MP",
            fnumber="16.0",
            exposure="5",
            iso="50",
            dt_original=datetime(2017, 12, 29, 11, 2, 22).timestamp(),
            dt_digitized=datetime(2017, 12, 29, 11, 2, 22).timestamp(),
            height=1,
            width=1,
        ),
    ),

])
def test_getexif(name: str, expected: Exif):
    pkg = resources.files("tests.data.images")
    with pkg.joinpath(name).open("rb") as content:
        actual = metadata._getexif(content)

    assert actual == expected


def test_getexif_when_there_is_no_exif(image_content: BytesIO):
    assert metadata._getexif(image_content) is None


def test_getexif_when_content_is_broken():
    content = BytesIO(b"Dummy content")
    assert metadata._getexif(content) is None
