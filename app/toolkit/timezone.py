from __future__ import annotations

from datetime import UTC, datetime

__all__ = [
    "EPOCH",
    "fromtimestamp",
    "now",
]

EPOCH = datetime.fromtimestamp(0, tz=UTC)


def fromtimestamp(ts: int | float) -> datetime:
    """Return UTC datetime from UTC timestamp."""
    return datetime.fromtimestamp(ts, tz=UTC)


def now() -> datetime:
    """Return an aware datetime."""
    return datetime.now(UTC)
