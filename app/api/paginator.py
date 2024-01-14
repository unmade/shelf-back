from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    page: int
    items: list[T]


def get_offset(page: int, size: int) -> int:
    """Calculates offset based on page number and page size."""
    assert page > 0, "'page' arg must be greater than 0."
    assert size > 0, "'size' arg must be greater than 0."
    return (page - 1) * size
