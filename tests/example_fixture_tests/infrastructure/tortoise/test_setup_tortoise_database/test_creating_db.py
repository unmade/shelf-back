from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import FixtureRequest

    from app.config import SQLiteConfig


def test(request: FixtureRequest, sqlite_config: SQLiteConfig):
    # WHEN
    request.getfixturevalue("setup_tortoise_database")

    # THEN - no error means it passed (setup is effectively a no-op)
    assert sqlite_config.db_url.startswith("sqlite://")
