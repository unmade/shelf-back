from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING

import pytest
from tortoise import Tortoise

from app.infrastructure.database.tortoise import TortoiseDatabase

if TYPE_CHECKING:
    from pytest import FixtureRequest, Pytester

pytestmark = [pytest.mark.metatest]


class TestSetupTortoiseDatabase:
    EXAMPLES = PurePath("infrastructure/tortoise/test_setup_tortoise_database")

    def test_creating_db(self, pytester: Pytester):
        pytester.makeconftest("""
            pytest_plugins = ["tests.conftest"]
        """)
        pytester.copy_example(str(self.EXAMPLES / "test_creating_db.py"))
        result = pytester.runpytest()
        result.assert_outcomes(passed=1)


@pytest.mark.anyio
class TestTortoiseDatabase:
    def test_accessing_without_marker(self, request: FixtureRequest):
        with pytest.raises(RuntimeError) as excinfo:
            request.getfixturevalue("tortoise_database")
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
        async for tx in tortoise_database.atomic():
            assert tx is not None

    @pytest.mark.database
    async def test_schema_created(self, tortoise_database: TortoiseDatabase):
        assert Tortoise.apps is not None
        models = Tortoise.apps["models"]
        assert "User" in models
        assert "File" in models
        assert "Namespace" in models
