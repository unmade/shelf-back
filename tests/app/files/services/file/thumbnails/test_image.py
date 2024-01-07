from __future__ import annotations

from importlib import resources
from io import BytesIO
from typing import TYPE_CHECKING

import pytest
from PIL import Image

from app.app.files.domain.file import File
from app.app.files.services.file.thumbnails.image import thumbnail_image

if TYPE_CHECKING:
    from app.app.files.domain import IFileContent


class TestImageThumbnail:
    pkg = resources.files("tests.data.images")

    def test_on_regular_image(self, image_content: IFileContent):
        thumbnail = thumbnail_image(image_content.file, size=128)
        assert len(thumbnail) == 112

    def test_on_animated_image(self):
        size = 64
        name = "animated.gif"
        with self.pkg.joinpath(name).open("rb") as content:
            thumbnail = thumbnail_image(content, size=size)

        assert len(thumbnail) == 12086

    def test_animated_image_stays_the_same_on_upscale(self):
        size = 512
        name = "animated.gif"
        with self.pkg.joinpath(name).open("rb") as content:
            thumbnail = thumbnail_image(content, size=size)

        assert len(thumbnail) == 33981

    @pytest.mark.parametrize(["size", "dimensions"], [
        (256, (192, 256)),
        (2048, (480, 640)),
    ])
    def test_should_downscale_only(self, size: int, dimensions: tuple[int, int]):
        name = "park_v1_downscaled.jpeg"
        with self.pkg.joinpath(name).open("rb") as content:
            thumbnail = thumbnail_image(content, size=size)
        with Image.open(BytesIO(thumbnail)) as im:
            assert im.size == dimensions

    def test_but_file_is_not_an_image(self):
        with pytest.raises(File.ThumbnailUnavailable):
            thumbnail_image(BytesIO(), size=128)
