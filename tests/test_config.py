from __future__ import annotations

from datetime import timedelta

import pytest

from app.config import _BASE_DIR, TTL, AbsPath, BytesSize, StringList


class TestAbsPath:
    @pytest.mark.parametrize(["given", "expected"], [
        ("./app", str(_BASE_DIR / "./app")),
        ("app", str(_BASE_DIR / "./app")),
        ("/usr/bin/src", "/usr/bin/src"),
    ])
    def test_converting_to_absolute_path(self, given: str, expected: str):
        assert AbsPath.validate(given) == expected

    def test_when_validating_non_str(self):
        with pytest.raises(TypeError) as excinfo:
            AbsPath.validate(1)
        assert str(excinfo.value) == "string required"

    def test_representation(self):
        assert repr(AbsPath("/usr/bin/src")) == "AbsPath('/usr/bin/src')"


class TestBytesSize:
    @pytest.mark.parametrize(["given", "expected"], [
        (512, 512),
        ("1KB", 1024),
    ])
    def test_validate(self, given: int | str, expected: str):
        assert BytesSize.validate(given) == expected

    def test_validate_invalid_value(self):
        with pytest.raises(TypeError) as excinfo:
            BytesSize.validate(1.5)
        assert str(excinfo.value) == "string or integer required"

    @pytest.mark.parametrize(["given", "expected"], [
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
    def test_from_string(self, given: str, expected: str):
        assert BytesSize.from_string(given) == expected

    @pytest.mark.parametrize("given", [
        "",
        "KB",
        "1.5.KB",
        "1.5.0KB",
        "1 KB",
        "-1KB",
    ])
    def test_from_string_when_value_is_invalid(self, given: str):
        with pytest.raises(ValueError) as excinfo:
            BytesSize.from_string(given)
        msg = 'string in a valid format required (e.g. "1KB", "1.5GB")'
        assert str(excinfo.value) == msg

    def test_representation(self):
        assert repr(BytesSize(256)) == "BytesSize(256)"


class TestStringList:
    @pytest.mark.parametrize(["given", "expected"], [
        ("single", ["single"]),
        ("", [""]),
        ("first,second", ["first", "second"]),
        (["first", "second"], ["first", "second"]),
    ])
    def test_converting_to_list(self, given, expected):
        assert StringList.validate(given) == expected

    def test_when_validating_non_list(self):
        with pytest.raises(TypeError) as excinfo:
            StringList.validate(1)
        assert str(excinfo.value) == "list or string required"

    def test_representation(self):
        assert repr(StringList(["single"])) == "StringList(['single'])"


class TestTTL:
    @pytest.mark.parametrize(["given", "expected"], [
        (timedelta(minutes=5), timedelta(minutes=5)),
        ("1h", timedelta(hours=1)),
    ])
    def test_validate(self, given: str | timedelta, expected: str):
        assert TTL.validate(given) == expected

    def test_validate_invalid_value(self):
        with pytest.raises(TypeError) as excinfo:
            TTL.validate(object())
        assert str(excinfo.value) == "string or timedelta required"

    @pytest.mark.parametrize(["given", "expected"], [
        ("1s", timedelta(seconds=1)),
        ("2m", timedelta(minutes=2)),
        ("4h", timedelta(hours=4)),
        ("7d", timedelta(days=7)),
        ("2h30s", timedelta(hours=2, seconds=30)),
        (" 1d2H30m15S ", timedelta(days=1, hours=2, minutes=30, seconds=15)),
    ])
    def test_from_string(self, given: str, expected: str):
        assert TTL.from_string(given) == expected

    @pytest.mark.parametrize("given", [
        "",
        "1",
        "s",
        "1.5s",
        "-1s",
        "1 d",
        "2h1d",
    ])
    def test_from_string_when_value_is_invalid(self, given: str):
        with pytest.raises(ValueError) as excinfo:
            TTL.from_string(given)
        msg = 'string in a valid format required (e.g. "1d6h30m15s", "2h30m", "15m")'
        assert str(excinfo.value) == msg
