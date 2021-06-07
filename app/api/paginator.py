from __future__ import annotations

from typing import Generic, TypeVar

from fastapi import Query
from pydantic.generics import GenericModel

T = TypeVar("T")

PageParam = Query(1, ge=1, description="Page number")
PageSizeParam = Query(25, ge=5, le=100, description="Page size")


class Page(GenericModel, Generic[T]):
    page: int
    count: int
    results: list[T]


def get_offset(page: int, size: int) -> int:
    """
    Calculates offset based on page number and page size.

    Args:
        page (int): Page number.
        size (int): Page size.

    Returns:
        int: Offset.
    """
    assert page > 0, "'page' arg must be greater than 0."
    assert size > 0, "'size' arg must be greater than 0."
    return (page - 1) * size
