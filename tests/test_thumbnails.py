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


def test_thumbnail(image_content: IO[bytes]):
    thumbnail = thumbnails.thumbnail(image_content, size=128)
    assert len(thumbnail) == 112


def test_thumbnail_on_animated_image():
    name = "animated.gif"
    size = 64
    pkg = resources.files("tests.data.images")
    with pkg.joinpath(name).open("rb") as content:
        thumbnail = thumbnails.thumbnail(content, size=size)

    assert len(thumbnail) == 19246


@pytest.mark.parametrize(["size", "dimensions"], [
    (256, (192, 256)),
    (2048, (480, 640)),
])
def test_thumbnail_should_downscale_only(size, dimensions):
    name = "park_v1_downscaled.jpeg"
    pkg = resources.files("tests.data.images")
    with pkg.joinpath(name).open("rb") as content:
        thumbnail = thumbnails.thumbnail(content, size=size)
    with Image.open(BytesIO(thumbnail)) as im:
        assert im.size == dimensions


def test_thumbnail_but_file_is_not_an_image():
    with pytest.raises(errors.ThumbnailUnavailable):
        thumbnails.thumbnail(BytesIO(), size=128)
