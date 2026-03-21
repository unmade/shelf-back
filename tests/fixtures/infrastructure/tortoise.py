from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest
from tortoise import Tortoise, connections

from app.config import SQLiteConfig
from app.infrastructure.database.tortoise import TortoiseDatabase

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pytest import FixtureRequest


@pytest.fixture(scope="session")
def sqlite_config(tmp_path_factory: pytest.TempPathFactory) -> SQLiteConfig:
    db_path = tmp_path_factory.mktemp("tortoise") / "test.db"
    return SQLiteConfig(db_url=f"sqlite://{db_path}")


@pytest.fixture(scope="session")
def setup_tortoise_database(sqlite_config: SQLiteConfig) -> None:
    """
    Creates test database and applies schema via Tortoise generate_schemas.
    This is a no-op, since the session-scoped _tortoise_database fixture
    handles init + schema creation.
    """


@pytest.fixture(autouse=True)
def flush_tortoise_database_if_needed(request: FixtureRequest):
    """Truncates all tables after each transactional test."""
    try:
        yield
    finally:
        if marker := request.node.get_closest_marker("database"):
            if marker.kwargs.get("transaction", False):
                if Tortoise.apps is not None:
                    session_conn = request.getfixturevalue("_session_tortoise_conn")
                    for model_cls in Tortoise.apps["models"].values():
                        table = getattr(model_cls, "Meta", None)
                        if table and hasattr(table, "table"):
                            session_conn.execute(
                                f'DELETE FROM "{table.table}"'
                            )
                    session_conn.commit()


@pytest.fixture(scope="session")
def _session_tortoise_conn(sqlite_config: SQLiteConfig):
    """Returns a sync sqlite3 connection for cleanup after transactional tests."""
    db_path = sqlite_config.db_url.replace("sqlite://", "")
    conn = sqlite3.connect(db_path)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
async def _tortoise_database(
    sqlite_config: SQLiteConfig,
) -> AsyncIterator[TortoiseDatabase]:
    """Returns a TortoiseDatabase with an active connection and schema."""
    db = TortoiseDatabase(sqlite_config)
    async with db:
        await db.migrate()
        yield db


@pytest.fixture
async def _tx_tortoise_database(
    _tortoise_database: TortoiseDatabase,
) -> AsyncIterator[TortoiseDatabase]:
    """Yields a transactional database that rollbacks after each test."""
    conn = connections.get("default")
    tx_ctx = conn._in_transaction()
    await tx_ctx.__aenter__()
    try:
        yield _tortoise_database
    finally:
        await tx_ctx.__aexit__(Exception, None, None)


@pytest.fixture
def tortoise_database(request: FixtureRequest, setup_tortoise_database):
    """
    Returns regular or a transactional TortoiseDatabase based on a database marker.
    """
    marker = request.node.get_closest_marker("database")
    if not marker:
        raise RuntimeError("Access to the database without `database` marker!")

    if marker.kwargs.get("transaction", False):
        yield request.getfixturevalue("_tortoise_database")
    else:
        yield request.getfixturevalue("_tx_tortoise_database")
