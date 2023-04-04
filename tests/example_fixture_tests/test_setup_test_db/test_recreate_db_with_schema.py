from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import TYPE_CHECKING, Iterator

import edgedb
import pytest

from app.config import config

if TYPE_CHECKING:
    from edgedb import Client
    from pytest import FixtureRequest


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
def db_dsn(db_dsn):
    """Redefine `db_dsn` with a unique database name to test `setup_test_db` fixture."""
    server_dsn, dsn, db_name = db_dsn
    name = f"db_{uuid.uuid4().hex}"
    return server_dsn, dsn.replace(db_name, name), name


@contextlib.contextmanager
def create_db_client(dsn: str) -> Iterator[Client]:
    db_config = config.database.copy(update={"dsn": dsn, "edgedb_max_concurrency": 1})
    with edgedb.create_client(
        dsn=db_config.dsn,
        max_concurrency=db_config.edgedb_max_concurrency,
        tls_ca_file=db_config.edgedb_tls_ca_file,
        tls_security=db_config.edgedb_tls_security,
    ) as client:
        yield client


@pytest.mark.database
def test_recreates_db_and_applies_migration(request: FixtureRequest, db_dsn):
    server_dsn, dsn, db_name = db_dsn
    with create_db_client(server_dsn) as db_client:
        db_client.execute(f"CREATE DATABASE {db_name};")

    request.getfixturevalue("setup_test_db")

    with create_db_client(dsn) as db_client:
        assert len(db_client.query("SELECT File")) == 0

    with create_db_client(server_dsn) as db_client:
        db_client.execute(f"DROP DATABASE {db_name};")
