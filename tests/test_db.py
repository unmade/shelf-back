from __future__ import annotations

from typing import Optional, Union

import pytest

from app import db


@pytest.mark.parametrize(["pytype", "dbtype"], [
    (str, '<REQUIRED str>'),
    (Optional[str], '<OPTIONAL str>'),
    (Union[None, str], '<OPTIONAL str>'),
    (Union[str, None], '<OPTIONAL str>'),
])
def test_autocast(pytype, dbtype) -> None:
    assert db.autocast(pytype) == dbtype


def test_autocast_but_type_is_unsupported() -> None:
    with pytest.raises(TypeError) as excinfo:
        db.autocast(list[int])

    message = "Can't cast python type `list[int]` to EdgeDB type."
    assert str(excinfo.value) == message


def test_autocast_but_type_is_union() -> None:
    with pytest.raises(TypeError) as excinfo:
        db.autocast(Union[int, float])

    message = "Can't cast python type `typing.Union[int, float]` to EdgeDB type."
    assert str(excinfo.value) == message


def test_autocast_but_type_is_invalid() -> None:
    with pytest.raises(TypeError) as excinfo:
        db.autocast("invalid type")

    message = "Can't cast python type `invalid type` to EdgeDB type."
    assert str(excinfo.value) == message
