from __future__ import annotations

import pytest

from app.api.paginator import get_offset


@pytest.mark.parametrize(["page", "size", "offset"], [
    (1, 5, 0),
    (2, 5, 5),
])
def test_get_offset(page, size, offset) -> None:
    assert get_offset(page, size) == offset


def test_get_offset_but_page_arg_is_invalid() -> None:
    with pytest.raises(AssertionError) as excinfo:
        get_offset(0, 5)

    assert str(excinfo.value) == "'page' arg must be greater than 0."


def test_get_offset_but_size_arg_is_invalid() -> None:
    with pytest.raises(AssertionError) as excinfo:
        get_offset(1, 0)

    assert str(excinfo.value) == "'size' arg must be greater than 0."
