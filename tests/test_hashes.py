from __future__ import annotations

from importlib import resources
from io import BytesIO

import pytest

from app import hashes


def test_dhash_for_image():
    with resources.open_binary("tests.data.images", "baikal_v1.jpeg") as im:
        assert hashes.dhash(im, mediatype="image/jpeg")


def test_dhash_but_image_is_broken():
    content = BytesIO(b"Dummy content")
    assert hashes.dhash(content, mediatype="image/jpeg") is None


def test_dhash_but_mediatype_is_unsupported():
    assert hashes.dhash(BytesIO(b"Hello, world"), mediatype="plain/text") is None


@pytest.mark.parametrize(["name_a", "name_b", "delta"], [
    ("baikal_v1.jpeg", "baikal_v2.jpeg", 1),
    ("baikal_v1.jpeg", "baikal_v3.jpeg", 24),
    ("park_v1.jpeg", "park_v2.jpeg", 7),
    ("park_v1.jpeg", "park_v1_downscaled.jpeg", 0),
])
def test_dhash_image(name_a, name_b, delta):
    with resources.open_binary("tests.data.images", name_a) as image_a:
        hash_a = hashes.dhash_image(image_a)

    with resources.open_binary("tests.data.images", name_b) as image_b:
        hash_b = hashes.dhash_image(image_b)

    assert (hash_a ^ hash_b).bit_count() == delta


def test_dhash_image_but_content_is_broken():
    content = BytesIO(b"Dummy content")
    with pytest.raises(hashes.UnhashableContent):
        hashes.dhash_image(content)
