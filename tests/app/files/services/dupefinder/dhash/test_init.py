from __future__ import annotations

from io import BytesIO
from unittest import mock

import pytest

from app.app.files.services.dupefinder import dhash

pytestmark = [pytest.mark.asyncio]


class TestDHash:
    async def test_image(self):
        # GIVEN
        content = mock.MagicMock()
        target_guess = "app.app.files.domain.mediatypes.guess"
        target_dhash = "app.app.files.services.dupefinder.dhash.dhash_image"
        # WHEN
        with (
            mock.patch(target_guess, return_value="image/jpeg") as guess_mock,
            mock.patch(target_dhash) as dhash_image_mock,
        ):
            result = await dhash.dhash(content)
        # THEN
        assert result == dhash_image_mock.return_value
        guess_mock.assert_called_once_with(content)
        dhash_image_mock.assert_called_once_with(content)

    async def test_when_mediatype_is_unsupported(self):
        content = BytesIO(b"Hello, world")
        value = await dhash.dhash(content)
        assert value is None
