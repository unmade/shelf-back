from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING

import pytest
from gel.asyncio_client import AsyncIOClient, AsyncIOIteration

from app.infrastructure.database.gel import GelDatabase
from app.infrastructure.database.gel.db import db_context

if TYPE_CHECKING:
    from pytest import FixtureRequest, Pytester

pytestmark = [pytest.mark.metatest]


class TestSetupGelDatabase:
    EXAMPLES = PurePath("infrastructure/gel/test_setup_gel_database")

    @pytest.mark.parametrize("options", ["", "--reuse-db"])
    def test_creating_db(self, pytester: Pytester, options: str):
        pytester.makeconftest("""
            pytest_plugins = ["tests.conftest"]
        """)
        pytester.copy_example(str(self.EXAMPLES / "test_creating_db.py"))
        result = pytester.runpytest(*options.split())
        result.assert_outcomes(passed=1)

    def test_recreating_db_with_schema(self, pytester: Pytester):
        pytester.makeconftest("""
            pytest_plugins = ["tests.conftest"]
        """)
        pytester.copy_example(str(self.EXAMPLES / "test_recreating_db_with_schema.py"))
        result = pytester.runpytest()
        result.assert_outcomes(passed=1)

    def test_reusing_db(self, pytester: Pytester):
        pytester.makeconftest("""
            pytest_plugins = ["tests.conftest"]
        """)
        pytester.copy_example(str(self.EXAMPLES / "test_reusing_db.py"))
        result = pytester.runpytest("--reuse-db")
        result.assert_outcomes(passed=1)


@pytest.mark.anyio
class TestGelDatabase:
    def test_accessing_without_marker(self, request: FixtureRequest):
        with pytest.raises(RuntimeError) as excinfo:
            request.getfixturevalue("gel_database")
        assert str(excinfo.value) == "Access to the database without `database` marker!"

    @pytest.mark.database
    async def test_database_marker(self, gel_database: GelDatabase):
        assert isinstance(gel_database, GelDatabase)
        assert isinstance(db_context.get(), AsyncIOIteration)

    @pytest.mark.database(transaction=True)
    async def test_when_database_marker_has_transaction(
        self, gel_database: GelDatabase
    ):
        assert isinstance(gel_database, GelDatabase)
        assert isinstance(db_context.get(), AsyncIOClient)
