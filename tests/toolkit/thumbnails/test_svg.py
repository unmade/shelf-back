from __future__ import annotations

from importlib import resources
from typing import TYPE_CHECKING

from app.toolkit.mediatypes import MediaType
from app.toolkit.thumbnails.svg import thumbnail_svg

if TYPE_CHECKING:
    from app.app.blobs.domain import IBlobContent


class TestSVGThumbnail:
    pkg = resources.files("tests.data.images")

    def test(self, svg_content: IBlobContent):
        thumbnail, mediatype = thumbnail_svg(svg_content.file)
        assert len(thumbnail) == 4207
        assert mediatype == MediaType.IMAGE_SVG
