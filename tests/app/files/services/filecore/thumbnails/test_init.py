from __future__ import annotations

from unittest import mock

import pytest

from app.app.files.services.filecore import thumbnails


class TestIsSupported:
    @pytest.mark.parametrize(["mediatype", "supported"], [
        ("image/jpeg", True),
        ("plain/text", False),
    ])
    def test(self, mediatype: str, supported: bool):
        assert thumbnails.is_supported(mediatype) is supported


@pytest.mark.asyncio
class TestThumbnail:
    async def test_text(self):
        # GIVEN
        content = mock.MagicMock()
        target_guess = "app.app.files.domain.mediatypes.guess"
        target_image = "app.app.files.services.filecore.thumbnails.thumbnail_image"
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
        target_guess = "app.app.files.domain.mediatypes.guess"
        target_image = "app.app.files.services.filecore.thumbnails.thumbnail_image"
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
        target_guess = "app.app.files.domain.mediatypes.guess"
        target_pdf = "app.app.files.services.filecore.thumbnails.thumbnail_pdf"
        # WHEN
        with (
            mock.patch(target_guess, return_value="application/pdf"),
            mock.patch(target_pdf) as pdf_mock,
        ):
            result = await thumbnails.thumbnail(content, size=32)
        # THEN
        assert result == pdf_mock.return_value
        pdf_mock.assert_called_once_with(content, size=32, mediatype="application/pdf")
