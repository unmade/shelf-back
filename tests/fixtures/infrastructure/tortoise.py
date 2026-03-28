from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from tortoise.contrib.test import tortoise_test_context, truncate_all_models
from tortoise.transactions import in_transaction

from app.config import PostgresConfig, SQLiteConfig
from app.infrastructure.database.tortoise import TortoiseDatabase
from app.infrastructure.database.tortoise.db import TORTOISE_MODELS

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pytest import FixtureRequest, MarkDecorator

DEFAULT_DB_URL = "sqlite://:memory:?install_regexp_functions=true"


def _db_url() -> str:
    return os.environ.get("TORTOISE_TEST_DB", DEFAULT_DB_URL)


def _make_config() -> PostgresConfig | SQLiteConfig:
    db_url = _db_url()
    if db_url.startswith("postgres"):
        return PostgresConfig(db_url=db_url)  # pragma: no cover
    return SQLiteConfig(db_url=db_url)


@pytest.fixture(scope="session")
async def _tortoise_ctx() -> AsyncIterator[None]:
    """Initialize Tortoise ORM and generate schemas once for the session."""
    async with tortoise_test_context(modules=TORTOISE_MODELS, db_url=_db_url()):
        yield


@pytest.fixture
def database_marker(request: FixtureRequest):
    marker = request.node.get_closest_marker("database")
    if not marker:  # pragma: no branch
        raise RuntimeError("Access to the database without `database` marker!")
    return marker


@pytest.fixture
async def tortoise_database(
    _tortoise_ctx,
    database_marker: MarkDecorator,
) -> AsyncIterator[TortoiseDatabase]:
    """
    Returns a TortoiseDatabase with per-test isolation.

    Requires the ``database`` marker. The schema is created once per session
    via ``tortoise_test_context``.

    By default, each test runs inside a transaction that is rolled back on
    teardown. For tests that need real commits (e.g. concurrency tests), use
    ``@pytest.mark.database(transaction=True)`` — those tests truncate all
    tables on teardown instead.

    Set ``TORTOISE_TEST_DB`` to test against a different backend.
    """
    db = TortoiseDatabase(_make_config())

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
