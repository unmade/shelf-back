from __future__ import annotations

from datetime import UTC, datetime

from dateutil import tz


def now() -> datetime:
    """Return an aware datetime."""
    return datetime.now(UTC).replace(tzinfo=tz.UTC)
