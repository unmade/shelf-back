from __future__ import annotations

from datetime import UTC, datetime

from dateutil import tz
from dateutil.tz.tz import EPOCH

__all__ = [
    "EPOCH",
    "fromtimestamp",
    "now",
]


def fromtimestamp(ts: int | float) -> datetime:
    """Return UTC datetime from UTC timestamp."""
    return datetime.fromtimestamp(ts, tz=UTC)


def now() -> datetime:
    """Return an aware datetime."""
    return datetime.now(UTC).replace(tzinfo=tz.UTC)
