from __future__ import annotations

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
def test_get_bool(given, expected) -> None:
    with mock.patch("os.getenv", return_value=given):
        value = config._get_bool("DEBUG")
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
def test_get_list(given, default, expected) -> None:
    with mock.patch("os.getenv", return_value=given):
        value = config._get_list("WORDS", default=default)
    assert value == expected
