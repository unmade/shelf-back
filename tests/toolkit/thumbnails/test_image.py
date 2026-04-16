from __future__ import annotations

from importlib import resources
from io import BytesIO
from typing import TYPE_CHECKING

import pytest
from PIL import Image

from app.toolkit.mediatypes import MediaType
from app.toolkit.thumbnails import ThumbnailUnavailable
from app.toolkit.thumbnails.image import thumbnail_image

if TYPE_CHECKING:
    from app.app.blobs.domain import IBlobContent


class TestImageThumbnail:
    pkg = resources.files("tests.data.images")

    def test_on_regular_image(self, image_content: IBlobContent):
        thumbnail, mediatype = thumbnail_image(image_content.file, size=128)
        assert len(thumbnail) == 112
        assert mediatype == MediaType.IMAGE_WEBP

    def test_on_animated_image(self):
        size = 64
        name = "animated.gif"
        with self.pkg.joinpath(name).open("rb") as content:
            thumbnail, mediatype = thumbnail_image(content, size=size)

        assert len(thumbnail) == 12086
        assert mediatype == MediaType.IMAGE_WEBP

    def test_animated_image_stays_the_same_on_upscale(self):
        size = 512
        name = "animated.gif"
        with self.pkg.joinpath(name).open("rb") as content:
            thumbnail, mediatype = thumbnail_image(content, size=size)

        assert len(thumbnail) == 33981
        assert mediatype == MediaType.IMAGE_GIF

    @pytest.mark.parametrize(["size", "dimensions"], [
        (256, (192, 256)),
        (2048, (480, 640)),
    ])
    def test_should_downscale_only(self, size: int, dimensions: tuple[int, int]):
        name = "park_v1_downscaled.jpeg"
        with self.pkg.joinpath(name).open("rb") as content:
            thumbnail, mediatype = thumbnail_image(content, size=size)

        assert mediatype == MediaType.IMAGE_WEBP
        with Image.open(BytesIO(thumbnail)) as im:
            assert im.size == dimensions

    def test_but_file_is_not_an_image(self):
        with pytest.raises(ThumbnailUnavailable):
            thumbnail_image(BytesIO(), size=128)
