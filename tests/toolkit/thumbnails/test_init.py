from __future__ import annotations

from unittest import mock

import pytest

from app.toolkit import thumbnails


class TestIsSupported:
    @pytest.mark.parametrize(["mediatype", "supported"], [
        ("image/jpeg", True),
        ("plain/text", False),
    ])
    def test(self, mediatype: str, supported: bool):
        assert thumbnails.is_supported(mediatype) is supported


@pytest.mark.anyio
class TestThumbnail:
    async def test_text(self):
        # GIVEN
        content = mock.MagicMock()
        target_guess = "app.toolkit.thumbnails.mediatypes.guess"
        target_image = "app.toolkit.thumbnails.thumbnail_image"
        # WHEN
        with (
            mock.patch(target_guess, return_value="plain/text") as guess_mock,
            mock.patch(target_image) as image_mock,
        ):
            result = await thumbnails.thumbnail(content, size=32)
        # THEN
        assert result == image_mock.return_value
        guess_mock.assert_called_once_with(content)
        image_mock.assert_called_once_with(content, size=32)

    async def test_image(self):
        # GIVEN
        content = mock.MagicMock()
        target_guess = "app.toolkit.thumbnails.mediatypes.guess"
        target_image = "app.toolkit.thumbnails.thumbnail_image"
        # WHEN
        with (
            mock.patch(target_guess, return_value="image/jpeg") as guess_mock,
            mock.patch(target_image) as image_mock,
        ):
            result = await thumbnails.thumbnail(content, size=32)
        # THEN
        assert result == image_mock.return_value
        guess_mock.assert_called_once_with(content)
        image_mock.assert_called_once_with(content, size=32)

    async def test_pdf(self):
        # GIVEN
        content = mock.MagicMock()
        target_guess = "app.toolkit.thumbnails.mediatypes.guess"
        target_pdf = "app.toolkit.thumbnails.thumbnail_pdf"
        # WHEN
        with (
            mock.patch(target_guess, return_value="application/pdf"),
            mock.patch(target_pdf) as pdf_mock,
        ):
            result = await thumbnails.thumbnail(content, size=32)
        # THEN
        assert result == pdf_mock.return_value
        pdf_mock.assert_called_once_with(content, size=32, mediatype="application/pdf")

    async def test_svg(self):
        # GIVEN
        content = mock.MagicMock()
        target_guess = "app.toolkit.thumbnails.mediatypes.guess"
        target_svg = "app.toolkit.thumbnails.thumbnail_svg"
        # WHEN
        with (
            mock.patch(target_guess, return_value="image/svg+xml") as guess_mock,
            mock.patch(target_svg) as svg_mock,
        ):
            result = await thumbnails.thumbnail(content, size=32)
        # THEN
        assert result == svg_mock.return_value
        guess_mock.assert_called_once_with(content)
        svg_mock.assert_called_once_with(content)
