from __future__ import annotations

from io import BytesIO
from typing import IO
from unittest import mock

import pytest

from app.toolkit import metadata

pytestmark = [pytest.mark.anyio]


class TestLoad:
    async def test_image(self, image_content_with_exif: IO[bytes]):
        # GIVEN
        target_guess = "app.toolkit.metadata.mediatypes.guess"
        target_load = "app.toolkit.metadata.load_image_data"
        # WHEN
        with (
            mock.patch(target_guess, return_value="image/jpeg") as guess_mock,
            mock.patch(target_load) as load_image_mock,
        ):
            result = await metadata.load(image_content_with_exif)
        # THEN
        assert result == load_image_mock.return_value
        guess_mock.assert_called_once_with(image_content_with_exif)
        load_image_mock.assert_called_once_with(image_content_with_exif)

    async def test_when_mediatype_is_not_supported(self):
        data = await metadata.load(BytesIO(b"Hello, world"))
        assert data is None
