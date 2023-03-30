from __future__ import annotations

from importlib import resources
from io import BytesIO

import pytest

from app.app.files.services.dupefinder.dhash.image import dhash_image


class TestDHashImage:
    @pytest.mark.parametrize(["name_a", "name_b", "delta"], [
        ("baikal_v1.jpeg", "baikal_v2.jpeg", 1),
        ("baikal_v1.jpeg", "baikal_v3.jpeg", 24),
        ("park_v1.jpeg", "park_v2.jpeg", 7),
        ("park_v1.jpeg", "park_v1_downscaled.jpeg", 0),
    ])
    def test(self, name_a: str, name_b: str, delta: int):
        pkg = resources.files("tests.data.images")
        with pkg.joinpath(name_a).open('rb') as image_a:
            hash_a = dhash_image(image_a)

        with pkg.joinpath(name_b).open('rb') as image_b:
            hash_b = dhash_image(image_b)

        assert hash_a is not None
        assert hash_b is not None
        assert (hash_a ^ hash_b).bit_count() == delta

    def test_when_content_is_broken(self):
        content = BytesIO(b"Dummy content")
        result = dhash_image(content)
        assert result is None
