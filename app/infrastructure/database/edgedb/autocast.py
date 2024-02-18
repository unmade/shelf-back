from __future__ import annotations

from types import UnionType
from typing import Union

__all__ = ["autocast"]

_TYPE_NAME = {
    "bool": "bool",
    "datetime": "datetime",
    "float": "float64",
    "int": "int64",
    "str": "str",
    "UUID": "uuid",
}


def autocast(pytype) -> str:
    """
    Casts python type to appropriate EdgeDB type and returns it in formats:
      - '<REQUIRED str>'
      - '<OPTIONAL str>'

    Raises:
        TypeError: If type casting fails.
    """
    marker = "REQUIRED"
    typename = ""

    if hasattr(pytype, "__name__"):
        typename = pytype.__name__
    if getattr(pytype, "__origin__", None) is Union or isinstance(pytype, UnionType):
        args = pytype.__args__
        if len(args) == 2 and any(isinstance(None, arg) for arg in args):
            tp = args[1] if isinstance(None, args[0]) else args[0]
            typename = tp.__name__
            marker = "OPTIONAL"

    try:
        return f"<{marker} {_TYPE_NAME[typename]}>"
    except KeyError as exc:
        raise TypeError(f"Can't cast python type `{pytype}` to EdgeDB type.") from exc
