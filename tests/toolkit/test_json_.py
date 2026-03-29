from __future__ import annotations

from app.toolkit import json_


class TestDumps:
    def test_simple_dict(self):
        result = json_.dumps({"key": "value"})
        assert result == '{"key":"value"}'

    def test_list(self):
        result = json_.dumps([1, 2, 3])
        assert result == "[1,2,3]"

    def test_default(self):
        result = json_.dumps({"v": object()}, default=lambda _: "fallback")
        assert result == '{"v":"fallback"}'


class TestLoads:
    def test_from_str(self):
        result = json_.loads('{"key":"value"}')
        assert result == {"key": "value"}

    def test_from_bytes(self):
        result = json_.loads(b'{"key":"value"}')
        assert result == {"key": "value"}

    def test_list(self):
        result = json_.loads("[1,2,3]")
        assert result == [1, 2, 3]
