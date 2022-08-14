from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from app import config


@pytest.mark.parametrize(
    ["given", "expected"],
    [
        ("True", True),
        ("true", True),
        ("1", True),
        ("0", False),
        ("False", False),
        (None, False),
    ],
)
def test_get_bool(given: str | None, expected: bool):
    with mock.patch("os.getenv", return_value=given):
        value = config._get_bool("DEBUG")
    assert value == expected


@pytest.mark.parametrize(
    ["given", "expected"],
    [
        ("10", 10),
        (None, None),
    ],
)
def test_get_int_or_none(given: str | None, expected: bool):
    with mock.patch("os.getenv", return_value=given):
        value = config._get_int_or_none("DEBUG")
    assert value == expected


@pytest.mark.parametrize(
    ["given", "default", "expected"],
    [
        (None, None, []),
        (None, ["default"], ["default"]),
        ("item1,item2", None, ["item1", "item2"]),
        ("item1,item2", ["default"], ["item1", "item2"]),
        ("item1 ,item2", None, ["item1 ", "item2"]),
        ("item1", None, ["item1"]),
    ],
)
def test_get_list(given: str, default: list[str] | None, expected: list[str]):
    with mock.patch("os.getenv", return_value=given):
        value = config._get_list("WORDS", default=default)
    assert value == expected


@pytest.mark.parametrize(
    ["given", "expected"],
    [
        (None, None),
        ("./certs", "/usr/src/certs"),
        ("/usr/src/certs", "/usr/src/certs"),
    ],
)
def test_get_optional_path(given: str | None, expected: str | None):
    basepath = Path("/usr/src")
    with mock.patch("os.getenv", return_value=given):
        value = config._get_optional_path("PATH", basepath=basepath)
    assert value == expected
