from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest import Pytester

pytestmark = [pytest.mark.metatest]


@pytest.mark.database
@pytest.mark.parametrize("options", ["", "--reuse-db"])
def test_setup_test_db_creates_db(pytester: Pytester, options: str):
    pytester.makeconftest("""
        pytest_plugins = ["tests.conftest"]
    """)
    pytester.copy_example("test_setup_test_db/test_create_db.py")
    result = pytester.runpytest(*options.split())
    result.assert_outcomes(passed=1)


@pytest.mark.database
def test_setup_test_db_recreates_db(pytester: Pytester):
    pytester.makeconftest("""
        pytest_plugins = ["tests.conftest"]
    """)
    pytester.copy_example("test_setup_test_db/test_recreate_db.py")
    result = pytester.runpytest("--reuse-db")
    result.assert_outcomes(passed=1)


@pytest.mark.database
def test_setup_test_db_recreates_db_with_schema(pytester: Pytester):
    pytester.makeconftest("""
        pytest_plugins = ["tests.conftest"]
    """)
    pytester.copy_example("test_setup_test_db/test_recreate_db_with_schema.py")
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
