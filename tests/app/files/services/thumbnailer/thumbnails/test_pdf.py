from __future__ import annotations

from importlib import resources
from io import BytesIO

import pytest
from PIL import Image

from app.app.files.services.thumbnailer.thumbnails.pdf import thumbnail_pdf


class TestPDFThumbnail:
    pkg = resources.files("tests.data.pdf")

    @pytest.mark.parametrize(["name", "mediatype"], [
        ("example.pdf", "application/pdf"),
        ("example.epub", "application/epub+zip"),
    ])
    def test(self, name: str, mediatype: str):
        size = 64
        with self.pkg.joinpath(name).open("rb") as content:
            thumbnail = thumbnail_pdf(content, size=size, mediatype=mediatype)
        with Image.open(BytesIO(thumbnail)) as im:
            width, height = im.size
        assert width < 64
        assert height == 64

    def test_should_not_upscale(self):
        size = 2048
        name = "example.pdf"
        with self.pkg.joinpath(name).open("rb") as content:
            thumbnail = thumbnail_pdf(content, size=size, mediatype="application/pdf")
        with Image.open(BytesIO(thumbnail)) as im:
            width, height = im.size
        assert width < 842
        assert height == 842
