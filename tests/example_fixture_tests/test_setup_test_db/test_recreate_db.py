from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import TYPE_CHECKING, Iterator

import edgedb
import pytest

from app import config

if TYPE_CHECKING:
    from edgedb import BlockingIOConnection
    from pytest import FixtureRequest


@pytest.fixture(scope="session")
def event_loop():
    """
    Redefine event loop without closing it after tests. This is intentional,
    since event loop will be closed in the parent test.
    """
    loop = asyncio.get_event_loop()
    yield loop
    # don't close the loop since it will be managed by parent test


@pytest.fixture(scope="session")
def db_dsn(db_dsn):
    """Redefine `db_dsn` with a unique database name to test `setup_test_db` fixture."""
    server_dsn, dsn, db_name = db_dsn
    name = f"db_{uuid.uuid4().hex}"
    return server_dsn, dsn.replace(db_name, name), name


@contextlib.contextmanager
def connection(dsn: str) -> Iterator[BlockingIOConnection]:
    conn = edgedb.connect(dsn=dsn, tls_ca_file=config.DATABASE_TLS_CA_FILE)
    try:
        yield conn
    finally:
        conn.close()


@pytest.mark.database
def test_recreates_db(request: FixtureRequest, db_dsn):
    server_dsn, dsn, db_name = db_dsn
    with connection(server_dsn) as conn:
        conn.execute(f"CREATE DATABASE {db_name};")

    request.getfixturevalue("setup_test_db")

    with connection(dsn) as conn:
        with pytest.raises(edgedb.InvalidReferenceError) as excinfo:
            assert len(conn.query("SELECT File")) == 0

    assert str(excinfo.value) == "object type or alias 'default::File' does not exist"

    with connection(server_dsn) as conn:
        conn.execute(f"DROP DATABASE {db_name};")
