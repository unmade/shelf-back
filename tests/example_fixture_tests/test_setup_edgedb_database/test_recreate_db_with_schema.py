from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import TYPE_CHECKING, Iterator

import edgedb
import pytest

if TYPE_CHECKING:
    from edgedb import Client
    from pytest import FixtureRequest

    from app.config import EdgeDBConfig


@contextlib.contextmanager
def create_db_client(db_config: EdgeDBConfig) -> Iterator[Client]:
    with edgedb.create_client(
        dsn=db_config.dsn,
        max_concurrency=1,
        tls_ca_file=db_config.edgedb_tls_ca_file,
        tls_security=db_config.edgedb_tls_security,
    ) as client:
        yield client


@pytest.fixture(scope="session")
def event_loop():
    """
    Redefine event loop without closing it after tests. This is intentional,
    since event loop will be closed in the parent test.
    """
    loop = asyncio.get_event_loop_policy().get_event_loop()
    yield loop
    # don't close the loop since it will be managed by parent test


@pytest.fixture(scope="session")
def edgedb_config(edgedb_config: EdgeDBConfig):
    assert edgedb_config.dsn is not None
    db_name = f"db_{uuid.uuid4().hex}"
    return edgedb_config.copy(update={"dsn": edgedb_config.dsn.with_name(db_name)})


@pytest.mark.database
def test_recreates_db_and_applies_migration(
    request: FixtureRequest,
    edgedb_config: EdgeDBConfig
):
    # GIVEN
    assert edgedb_config.dsn is not None
    server_config = edgedb_config.copy(update={"dsn": edgedb_config.dsn.origin})
    with create_db_client(server_config) as db_client:
        db_client.execute(f"CREATE DATABASE {edgedb_config.dsn.name};")
    # WHEN
    request.getfixturevalue("setup_edgedb_database")
    # THEN
    with create_db_client(edgedb_config) as db_client:
        assert len(db_client.query("SELECT File")) == 0

    with create_db_client(server_config) as db_client:
        db_client.execute(f"DROP DATABASE {edgedb_config.dsn.name};")
