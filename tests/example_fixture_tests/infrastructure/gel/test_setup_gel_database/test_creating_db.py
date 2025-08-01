from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app.infrastructure.database.gel import GelDatabase

if TYPE_CHECKING:
    from pytest import FixtureRequest

    from app.config import GelConfig


@pytest.fixture(scope="session")
def gel_config(gel_config: GelConfig):
    assert gel_config.dsn is not None
    db_name = f"db_{uuid.uuid4().hex}"
    return gel_config.model_copy(
        update={
            "dsn": gel_config.dsn.with_name(db_name)
        }
    )


def test(request: FixtureRequest, gel_config: GelConfig):
    # GIVEN
    assert gel_config.dsn is not None
    server_db_cls = mock.MagicMock(GelDatabase)
    server_db_instance = server_db_cls.__aenter__.return_value

    db_cls = mock.MagicMock(GelDatabase)
    db_instance = db_cls.__aenter__.return_value

    target = "tests.fixtures.infrastructure.gel.GelDatabase"
    with mock.patch(target, side_effect=[server_db_cls, db_cls]):
        # WHEN
        request.getfixturevalue("setup_gel_database")

    # THEN
    server_db_instance.client.execute.assert_awaited_once_with(
        f"CREATE DATABASE {gel_config.dsn.name};"
    )
    db_instance.migrate.assert_awaited_once_with()
