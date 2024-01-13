from __future__ import annotations

from datetime import datetime
from importlib import resources
from io import BytesIO
from typing import TYPE_CHECKING

import pytest

from app.app.files.domain import Exif
from app.app.files.services.metadata.readers.image import load_image_data

if TYPE_CHECKING:
    from app.app.files.domain import IFileContent


class TestLoadImageData:
    @pytest.mark.parametrize(["name", "expected"], [
        (
            "exif_iphone_with_hdr_on.jpeg",
            Exif(
                type="exif",
                make="Apple",
                model="iPhone 6",
                focal_length_35mm=57,
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
                focal_length_35mm=28,
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
                focal_length=None,
                focal_length_35mm=None,
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
                focal_length=80,
                fnumber="16.0",
                exposure="5",
                iso="50",
                dt_original=datetime(2017, 12, 29, 11, 2, 22).timestamp(),
                dt_digitized=datetime(2017, 12, 29, 11, 2, 22).timestamp(),
                height=1,
                width=1,
            ),
        ),
        (
            "exif_broken_timestamp.jpg",
            Exif(
                type="exif",
                make="OLYMPUS IMAGING CORP.",
                model="E-M5",
                fnumber="4.0",
                focal_length=70,
                exposure="1/160",
                iso=None,
                dt_original=None,
                dt_digitized=None,
                height=1,
                width=1,
            ),
        ),
    ])
    def test(self, name: str, expected: Exif):
        pkg = resources.files("tests.data.images")
        with pkg.joinpath(name).open("rb") as content:
            actual = load_image_data(content)

        assert actual == expected

    def test_when_there_is_no_exif(self, image_content: IFileContent):
        assert load_image_data(image_content.file) is None

    def test_when_content_is_broken(self):
        content = BytesIO(b"Dummy content")
        assert load_image_data(content) is None
