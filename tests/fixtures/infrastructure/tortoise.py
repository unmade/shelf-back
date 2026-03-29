from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from tortoise.context import TortoiseContext
from tortoise.contrib.test import tortoise_test_context, truncate_all_models
from tortoise.transactions import in_transaction

from app.config import TortoiseConfig, config
from app.infrastructure.database.tortoise import TortoiseDatabase
from app.infrastructure.database.tortoise.db import TORTOISE_MODELS

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pytest import FixtureRequest, MarkDecorator, TempPathFactory


async def _drop_test_db(dsn: str) -> None:
    """Drop the test database if it exists, using Tortoise's own client."""
    async with TortoiseContext() as ctx:
        await ctx.init(db_url=dsn, modules={"models": TORTOISE_MODELS})
        conn = ctx.connections.get("default")
        await conn.db_delete()


def _make_tortoise_config(
    database: TortoiseConfig, tmp_path_factory: TempPathFactory
) -> TortoiseConfig:
    if database.dsn.is_memory():
        return database

    if database.dsn.is_sqlite():
        db_path = tmp_path_factory.mktemp("tortoise") / "shelf_test.sqlite3"
        dsn = database.dsn.with_name(f"/{db_path}")
    else:
        dsn = database.dsn.with_name(f"{database.dsn.name}_test")

    return database.model_copy(update={"dsn": dsn})


@pytest.fixture(scope="session")
def tortoise_config(tmp_path_factory: TempPathFactory) -> TortoiseConfig:
    assert isinstance(config.database, TortoiseConfig)
    return _make_tortoise_config(config.database, tmp_path_factory)


@pytest.fixture(scope="session")
async def _tortoise_ctx(tortoise_config: TortoiseConfig) -> AsyncIterator[None]:
    """Initialize Tortoise ORM and generate schemas once for the session."""
    await _drop_test_db(tortoise_config.dsn)
    async with tortoise_test_context(
        modules=TORTOISE_MODELS, db_url=tortoise_config.dsn
    ):
        yield


@pytest.fixture
def database_marker(request: FixtureRequest):
    marker = request.node.get_closest_marker("database")
    if not marker:
        raise RuntimeError("Access to the database without `database` marker!")
    return marker


@pytest.fixture
async def tortoise_database(
    tortoise_config: TortoiseConfig,
    database_marker: MarkDecorator,
    _tortoise_ctx,
) -> AsyncIterator[TortoiseDatabase]:
    """
    Returns a TortoiseDatabase with per-test isolation.

    Requires the ``database`` marker. The schema is created once per session
    via ``tortoise_test_context``.

    By default, each test runs inside a transaction that is rolled back on
    teardown. For tests that need real commits (e.g. concurrency tests), use
    ``@pytest.mark.database(transaction=True)`` — those tests truncate all
    tables on teardown instead.

    Set ``DATABASE__DB_URL`` to a Postgres DSN to test against Postgres.
    """
    db = TortoiseDatabase(tortoise_config)

    if database_marker.kwargs.get("transaction", False):
        try:
            yield db
        finally:
            await truncate_all_models()
    else:
        async with in_transaction("default") as tx:
            try:
                yield db
            finally:
                await tx.rollback()
