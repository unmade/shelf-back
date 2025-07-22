from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import gel
import pytest

from app.config import EdgeDBConfig, config
from app.infrastructure.database.edgedb import EdgeDBDatabase
from app.infrastructure.database.edgedb.db import db_context

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pytest import FixtureRequest


@pytest.fixture(scope="session")
def edgedb_config():
    assert config.database.dsn is not None
    db_name = f"{config.database.dsn.name}_test"
    return config.database.model_copy(
        update={
            "dsn": config.database.dsn.with_name(db_name),
            "edgedb_max_concurrency": 4
        }
    )


@pytest.fixture(scope="session")
def setup_edgedb_database(reuse_db: bool, edgedb_config: EdgeDBConfig) -> None:
    """
    Creates a test database and apply migration. If database already exists and
    no `--reuse-db` provided, then test database will be re-created.
    """
    async def _create_db():
        assert edgedb_config.dsn is not None
        db_name = edgedb_config.dsn.name
        server_conf = edgedb_config.model_copy(update={"dsn": edgedb_config.dsn.origin})
        created = True
        async with EdgeDBDatabase(server_conf) as db:
            try:
                await db.client.execute(f"CREATE DATABASE {db_name};")
            except gel.DuplicateDatabaseDefinitionError:
                if not reuse_db:
                    await db.client.execute(f"DROP DATABASE {db_name};")
                    await db.client.execute(f"CREATE DATABASE {db_name};")
                else:
                    created = False
        return created

    async def _migrate():
        async with EdgeDBDatabase(edgedb_config) as db:
            await db.migrate()

    # fixture is synchronous, cause pytest-asyncio doesn't work well with pytester
    should_migrate = asyncio.run(_create_db())
    if should_migrate:
        asyncio.run(_migrate())


@pytest.fixture(autouse=True)
def flush_edgedb_database_if_needed(request: FixtureRequest):
    """Flushes database after each tests."""
    try:
        yield
    finally:
        if marker := request.node.get_closest_marker("database"):
            if marker.kwargs.get("transaction", False):
                session_db_client = request.getfixturevalue("_session_sync_client")
                session_db_client.execute("""
                    DELETE Account;
                    DELETE AuditTrail;
                    DELETE AuditTrailAction;
                    DELETE File;
                    DELETE FileMetadata;
                    DELETE FilePendingDeletion;
                    DELETE Fingerprint;
                    DELETE MediaType;
                    DELETE Namespace;
                    DELETE SharedLink;
                    DELETE User;
                """)


@pytest.fixture(scope="session")
def _session_sync_client(edgedb_config: EdgeDBConfig):
    with gel.create_client(
        str(edgedb_config.dsn),
        max_concurrency=4,
        tls_ca_file=edgedb_config.edgedb_tls_ca_file,
        tls_security=edgedb_config.edgedb_tls_security,
    ) as client:
        yield client


@pytest.fixture(scope="session")
async def _database(edgedb_config: EdgeDBConfig):
    """Returns an EdgeDBDatabase instance."""
    return EdgeDBDatabase(edgedb_config)


@pytest.fixture
async def _tx_database(_database: EdgeDBDatabase) -> AsyncIterator[EdgeDBDatabase]:
    """Yields a transaction and rollback it after each test."""
    async for transaction in _database.client.transaction():
        transaction._managed = True
        token = db_context.set(transaction)
        try:
            yield _database
        finally:
            db_context.reset(token)
            await transaction._exit(Exception, None)


@pytest.fixture
def edgedb_database(request: FixtureRequest, setup_edgedb_database):
    """Returns regular or a transactional EdgeDBDatabase based on a database marker."""
    marker = request.node.get_closest_marker("database")
    if not marker:
        raise RuntimeError("Access to the database without `database` marker!")

    if marker.kwargs.get("transaction", False):
        yield request.getfixturevalue("_database")
    else:
        yield request.getfixturevalue("_tx_database")
