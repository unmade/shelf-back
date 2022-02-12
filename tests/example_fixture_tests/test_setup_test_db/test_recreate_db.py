from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import TYPE_CHECKING, Iterator

import edgedb
import pytest

from app import config

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
    with edgedb.create_client(
        dsn=dsn,
        max_concurrency=1,
        tls_ca_file=config.DATABASE_TLS_CA_FILE,
    ) as client:
        yield client


@pytest.mark.database
def test_recreates_db(request: FixtureRequest, db_dsn):
    server_dsn, dsn, db_name = db_dsn
    with create_db_client(server_dsn) as db_client:
        db_client.execute(f"CREATE DATABASE {db_name};")

    request.getfixturevalue("setup_test_db")

    with create_db_client(dsn) as db_client:
        with pytest.raises(edgedb.InvalidReferenceError) as excinfo:
            assert len(db_client.query("SELECT File")) == 0

    assert str(excinfo.value) == "object type or alias 'default::File' does not exist"

    with create_db_client(server_dsn) as db_client:
        db_client.execute(f"DROP DATABASE {db_name};")
