from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING

import pytest
from edgedb.asyncio_client import AsyncIOClient, AsyncIOIteration

from app.infrastructure.database.edgedb import EdgeDBDatabase
from app.infrastructure.database.edgedb.db import db_context

if TYPE_CHECKING:
    from pytest import FixtureRequest, Pytester

pytestmark = [pytest.mark.metatest]


class TestSetupEdgeDBDatabase:
    EXAMPLES = PurePath("infrastructure/edgedb/test_setup_edgedb_database")

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


@pytest.mark.usefixtures("anyio_backend")
class TestEdgeDBDatabase:
    def test_accessing_without_marker(self, request: FixtureRequest):
        with pytest.raises(RuntimeError) as excinfo:
            request.getfixturevalue("edgedb_database")
        assert str(excinfo.value) == "Access to the database without `database` marker!"

    @pytest.mark.database
    def test_database_marker(self, request: FixtureRequest):
        database = request.getfixturevalue("edgedb_database")
        assert isinstance(database, EdgeDBDatabase)
        assert isinstance(db_context.get(), AsyncIOIteration)

    @pytest.mark.database(transaction=True)
    def test_when_database_marker_has_transaction(self, request: FixtureRequest):
        database = request.getfixturevalue("edgedb_database")
        assert isinstance(database, EdgeDBDatabase)
        assert isinstance(db_context.get(), AsyncIOClient)
