from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest import mock

import edgedb
import pytest

from app.infrastructure.database.edgedb.db import EdgeDBDatabase

if TYPE_CHECKING:
    from pytest import FixtureRequest

    from app.config import EdgeDBConfig


@pytest.fixture(scope="session")
def edgedb_config(edgedb_config: EdgeDBConfig):
    assert edgedb_config.dsn is not None
    db_name = f"db_{uuid.uuid4().hex}"
    return edgedb_config.copy(update={"dsn": edgedb_config.dsn.with_name(db_name)})


def test(request: FixtureRequest, edgedb_config: EdgeDBConfig):
    # GIVEN
    assert edgedb_config.dsn is not None
    server_db_cls = mock.MagicMock(EdgeDBDatabase)
    server_db_instance = server_db_cls.__aenter__.return_value
    server_db_instance.client.execute.side_effect = [
        edgedb.DuplicateDatabaseDefinitionError
    ]

    db_cls = mock.MagicMock(EdgeDBDatabase)
    db_instance = db_cls.__aenter__.return_value

    target = "tests.fixtures.infrastructure.edgedb.EdgeDBDatabase"
    with mock.patch(target, side_effect=[server_db_cls, db_cls]):
        # WHEN
        request.getfixturevalue("setup_edgedb_database")

    # THEN
    server_db_instance.client.execute.assert_awaited_once_with(
        f"CREATE DATABASE {edgedb_config.dsn.name};"
    )

    db_instance.migrate.assert_not_awaited()
