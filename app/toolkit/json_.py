from __future__ import annotations

from typing import TYPE_CHECKING, Any

import orjson

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["dumps", "loads"]


def dumps(value: Any, *, default: Callable[[Any], Any] | None = None) -> str:
    """Serializes value to a JSON formatted str."""
    return orjson.dumps(value, default=default).decode()


def loads(value: str | bytes) -> Any:
    """Deserializes value containing a JSON document to a Python object."""
    return orjson.loads(value)
