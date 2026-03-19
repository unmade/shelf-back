from __future__ import annotations

from importlib import resources
from io import BytesIO

import pytest
from PIL import Image

from app.app.files.services.thumbnailer.thumbnails.pdf import thumbnail_pdf
from app.toolkit.mediatypes import MediaType


class TestPDFThumbnail:
    pkg = resources.files("tests.data.pdf")

    @pytest.mark.parametrize(["name", "mediatype"], [
        ("example.pdf", "application/pdf"),
        ("example.epub", "application/epub+zip"),
    ])
    def test(self, name: str, mediatype: str):
        size = 64
        with self.pkg.joinpath(name).open("rb") as content:
            result = thumbnail_pdf(content, size=size, mediatype=mediatype)

        thumbnail, thumbnail_mediatype = result
        with Image.open(BytesIO(thumbnail)) as im:
            width, height = im.size
        assert width < 64
        assert height == 64
        assert thumbnail_mediatype == MediaType.IMAGE_WEBP

    def test_should_not_upscale(self):
        size = 2048
        name = "example.pdf"
        with self.pkg.joinpath(name).open("rb") as content:
            result = thumbnail_pdf(content, size=size, mediatype="application/pdf")

        thumbnail, thumbnail_mediatype = result
        with Image.open(BytesIO(thumbnail)) as im:
            width, height = im.size
        assert width < 842
        assert height == 842
        assert thumbnail_mediatype == MediaType.IMAGE_WEBP
