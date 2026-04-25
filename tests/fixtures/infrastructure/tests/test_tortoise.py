from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from tortoise import Tortoise

from app.config import DatabaseDSN, TortoiseConfig
from app.infrastructure.database.tortoise import TortoiseDatabase
from tests.fixtures.infrastructure.tortoise import _make_tortoise_config

if TYPE_CHECKING:
    from pytest import FixtureRequest, TempPathFactory

pytestmark = [pytest.mark.metatest]


class TestTortoiseConfig:
    def test_returns_config_as_is_for_memory_dsn(
        self, tmp_path_factory: TempPathFactory,
    ):
        db_config = TortoiseConfig(dsn=DatabaseDSN("sqlite://:memory:"))
        result = _make_tortoise_config(db_config, tmp_path_factory)
        assert result is db_config

    def test_creates_temp_db_for_sqlite_dsn(
        self, tmp_path_factory: TempPathFactory,
    ):
        db_config = TortoiseConfig(dsn=DatabaseDSN("sqlite:///path/to/db.sqlite3"))
        result = _make_tortoise_config(db_config, tmp_path_factory)
        assert result is not db_config
        assert result.dsn.is_sqlite()
        assert str(tmp_path_factory.getbasetemp()) in str(result.dsn)
        assert result.dsn.endswith("shelf_test.sqlite3")

    def test_appends_test_suffix_for_non_sqlite_dsn(
        self, tmp_path_factory: TempPathFactory,
    ):
        db_config = TortoiseConfig(
            dsn=DatabaseDSN("postgres://user:pass@localhost:5432/shelf"),
        )
        result = _make_tortoise_config(db_config, tmp_path_factory)
        assert result.dsn.name == "shelf_test"


@pytest.mark.anyio
class TestTortoiseDatabase:
    def test_accessing_without_marker(self, request: FixtureRequest):
        with pytest.raises(RuntimeError) as excinfo:
            request.getfixturevalue("database_marker")
        assert str(excinfo.value) == "Access to the database without `database` marker!"

    @pytest.mark.database
    async def test_database_marker(self, tortoise_database: TortoiseDatabase):
        assert isinstance(tortoise_database, TortoiseDatabase)

    @pytest.mark.database(transaction=True)
    async def test_when_database_marker_has_transaction(
        self, tortoise_database: TortoiseDatabase,
    ):
        assert isinstance(tortoise_database, TortoiseDatabase)

    @pytest.mark.database
    async def test_atomic(self, tortoise_database: TortoiseDatabase):
        # GIVEN
        # WHEN
        async with tortoise_database.atomic() as tx:
            # THEN
            assert tx is not None

    @pytest.mark.database
    async def test_schema_created(self, tortoise_database: TortoiseDatabase):
        assert Tortoise.apps is not None
        models = Tortoise.apps["models"]
        assert "User" in models
        assert "File" in models
        assert "Namespace" in models
