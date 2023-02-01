from __future__ import annotations

from typing import Optional, Union

import pytest

from app.infrastructure.database.edgedb import autocast


@pytest.mark.parametrize(["pytype", "dbtype"], [
    (str, '<REQUIRED str>'),
    (Optional[str], '<OPTIONAL str>'),
    (Union[None, str], '<OPTIONAL str>'),
    (Union[str, None], '<OPTIONAL str>'),
    (str | None, '<OPTIONAL str>'),
])
def test_autocast(pytype, dbtype) -> None:
    assert autocast.autocast(pytype) == dbtype


def test_autocast_but_type_is_unsupported() -> None:
    with pytest.raises(TypeError) as excinfo:
        autocast.autocast(list[int])

    message = "Can't cast python type `list[int]` to EdgeDB type."
    assert str(excinfo.value) == message


@pytest.mark.parametrize(["pytype", "pytype_as_str"], [
    (Union[int, float], "typing.Union[int, float]"),
    (int | float, "int | float"),
])
def test_autocast_but_type_is_union(pytype, pytype_as_str) -> None:
    with pytest.raises(TypeError) as excinfo:
        autocast.autocast(pytype)

    message = f"Can't cast python type `{pytype_as_str}` to EdgeDB type."
    assert str(excinfo.value) == message


def test_autocast_but_type_is_invalid() -> None:
    with pytest.raises(TypeError) as excinfo:
        autocast.autocast("invalid type")

    message = "Can't cast python type `invalid type` to EdgeDB type."
    assert str(excinfo.value) == message
