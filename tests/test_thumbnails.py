from __future__ import annotations

from importlib import resources
from io import BytesIO
from typing import IO

import pytest
from PIL import Image

from app import errors, thumbnails


@pytest.mark.parametrize(["mediatype", "supported"], [
    ("image/jpeg", True),
    ("plain/text", False),
])
def test_is_supported(mediatype: str, supported: bool):
    assert thumbnails.is_supported(mediatype) is supported


class TestImageThumbnail:
    pkg = resources.files("tests.data.images")

    def test_on_regular_image(self, image_content: IO[bytes]):
        thumbnail = thumbnails.thumbnail(image_content, size=128)
        assert len(thumbnail) == 112

    def test_on_animated_image(self):
        size = 64
        name = "animated.gif"
        with self.pkg.joinpath(name).open("rb") as content:
            thumbnail = thumbnails.thumbnail(content, size=size)

        assert len(thumbnail) == 19246

    @pytest.mark.parametrize(["size", "dimensions"], [
        (256, (192, 256)),
        (2048, (480, 640)),
    ])
    def test_should_downscale_only(self, size: int, dimensions: tuple[int, int]):
        name = "park_v1_downscaled.jpeg"
        with self.pkg.joinpath(name).open("rb") as content:
            thumbnail = thumbnails.thumbnail(content, size=size)
        with Image.open(BytesIO(thumbnail)) as im:
            assert im.size == dimensions

    def test_but_file_is_not_an_image(self):
        with pytest.raises(errors.ThumbnailUnavailable):
            thumbnails.thumbnail(BytesIO(), size=128)


class TestPDFThumbnail:
    pkg = resources.files("tests.data.pdf")

    @pytest.mark.parametrize("name", ["example.pdf", "example.epub"])
    def test(self, name: str):
        size = 64
        with self.pkg.joinpath(name).open("rb") as content:
            thumbnail = thumbnails.thumbnail(content, size=size)
        with Image.open(BytesIO(thumbnail)) as im:
            width, height = im.size
        assert width < 64
        assert height == 64

    def test_should_not_upscale(self):
        size = 2048
        name = "example.pdf"
        with self.pkg.joinpath(name).open("rb") as content:
            thumbnail = thumbnails.thumbnail(content, size=size)
        with Image.open(BytesIO(thumbnail)) as im:
            width, height = im.size
        assert width < 842
        assert height == 842
