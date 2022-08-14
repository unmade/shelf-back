from __future__ import annotations

from datetime import datetime

from dateutil import tz


def now() -> datetime:
    """Return an aware datetime."""
    return datetime.utcnow().replace(tzinfo=tz.UTC)
