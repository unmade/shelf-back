from __future__ import annotations

from datetime import timedelta

import pytest

from app.config import (
    _BASE_DIR,
    _as_absolute_path,
    _parse_bytes_size,
    _parse_timedelta_from_str,
)


class TestAsAbsolutePath:
    @pytest.mark.parametrize(["given", "expected"], [
        (None, None),
        ("./app", str(_BASE_DIR / "./app")),
        ("app", str(_BASE_DIR / "./app")),
        ("/usr/bin/src", "/usr/bin/src"),
    ])
    def test(self, given: str, expected: str):
        assert _as_absolute_path(given) == expected


class TestParseBytesSize:
    @pytest.mark.parametrize(["given", "expected"], [
        (512, 512),
        ("0B", 0),
        ("1B", 1),
        ("256", 256),
        ("1kb", 1024),
        (" 1KB ", 1024),
        ("1.0KB", 1024),
        ("1.50KB", 1024 + 512),
        ("2MB", 2* 2**20),
        ("4GB", 4 * 2**30),
    ])
    def test(self, given: int | str, expected: str):
        assert _parse_bytes_size(given) == expected

    @pytest.mark.parametrize("given", [
        "",
        "KB",
        "1.5.KB",
        "1.5.0KB",
        "1 KB",
        "-1KB",
    ])
    def test_when_value_is_invalid(self, given: str):
        with pytest.raises(ValueError) as excinfo:
            _parse_bytes_size(given)
        msg = 'string in a valid format required (e.g. "1KB", "1.5GB")'
        assert str(excinfo.value) == msg

    def test_non_string_value(self):
        given = object()
        result = _parse_timedelta_from_str(given)
        assert result is given


class TestParseTimedeltaFromStr:
    @pytest.mark.parametrize(["given", "expected"], [
        ("1s", timedelta(seconds=1)),
        ("2m", timedelta(minutes=2)),
        ("4h", timedelta(hours=4)),
        ("7d", timedelta(days=7)),
        ("2h30s", timedelta(hours=2, seconds=30)),
        (" 1d2H30m15S ", timedelta(days=1, hours=2, minutes=30, seconds=15)),
    ])
    def test(self, given: str | timedelta, expected: str):
        assert _parse_timedelta_from_str(given) == expected

    @pytest.mark.parametrize("given", [
        "",
        "1",
        "s",
        "1.5s",
        "-1s",
        "1 d",
        "2h1d",
    ])
    def test_when_value_is_invalid(self, given: str):
        with pytest.raises(ValueError) as excinfo:
            _parse_timedelta_from_str(given)
        msg = 'string in a valid format required (e.g. "1d6h30m15s", "2h30m", "15m")'
        assert str(excinfo.value) == msg

    def test_non_string_value(self):
        given = object()
        result = _parse_timedelta_from_str(given)
        assert result is given
