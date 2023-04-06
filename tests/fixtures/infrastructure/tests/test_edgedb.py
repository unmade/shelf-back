from __future__ import annotations

from pathlib import PurePath
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest import Pytester

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
