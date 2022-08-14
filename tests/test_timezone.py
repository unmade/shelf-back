from __future__ import annotations

from app import timezone


def test_now() -> None:
    aware = timezone.now()
    assert aware.tzname() == "UTC"
