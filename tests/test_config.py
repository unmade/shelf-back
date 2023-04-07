from __future__ import annotations

import pytest

from app.config import _BASE_DIR, AbsPath, StringList


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
