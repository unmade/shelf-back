from __future__ import annotations

from importlib import resources
from typing import TYPE_CHECKING

from app.app.files.services.thumbnailer.thumbnails.svg import thumbnail_svg
from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from app.app.files.domain import IFileContent


class TestSVGThumbnail:
    pkg = resources.files("tests.data.images")

    def test(self, svg_content: IFileContent):
        thumbnail, mediatype = thumbnail_svg(svg_content.file)
        assert len(thumbnail) == 4207
        assert mediatype == MediaType.IMAGE_SVG
