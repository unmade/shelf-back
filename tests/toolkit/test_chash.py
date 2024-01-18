from __future__ import annotations

from io import BytesIO

import pytest

from app.toolkit import chash


class TestCHash:
    @pytest.mark.parametrize(["data", "expected_result"], [
        (b"", ""),
        (
            b"Hello, World!\n",
            "aa4aeabf82d0f32ed81807b2ddbb48e6d3bf58c7598a835651895e5ecb282e77",
        ),
    ])
    def test_on_empty_content(self, data: bytes, expected_result: str):
        content = BytesIO(data)
        result = chash.chash(content)
        assert result == expected_result

    def test_on_content_larger_than_one_chunk(self):
        # GIVEN
        _5_MB = 5 * 1024 * 1024
        value = b"Hello, World!\n"
        data = value * (_5_MB // len(value) + 1)
        assert len(data) > chash._DROPBOX_HASH_CHUNK_SIZE
        content = BytesIO(data)
        # WHEN
        res = chash.chash(content)
        # THEN
        assert res == "64044af8cfbdc9b0966b80ed6098465dd7b060fa627a5597979fb9dd607c66c5"
