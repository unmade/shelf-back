from __future__ import annotations

from typing import TYPE_CHECKING

import edgedb
import pytest

if TYPE_CHECKING:
    from pytest import Pytester
    from app.typedefs import DBPool, DBTransaction, DBPoolOrTransaction

pytestmark = [pytest.mark.metatest]


@pytest.mark.xfail(
    raises=RuntimeError,
    reason="missing 'database' marker",
    strict=True,
)
def test_can_not_use_db_pool_without_marker(db_pool):
    """Test raises RuntimError since it does not have a `database` marker."""


@pytest.mark.xfail(
    raises=RuntimeError,
    reason="missing 'transaction=True' flag",
    strict=True,
)
@pytest.mark.database
def test_can_not_use_db_pool_without_transaction_flag(db_pool):
    """Test raises RuntimeError since it does not have `transaction=True` flag."""


@pytest.mark.asyncio
@pytest.mark.database(transaction=True)
async def test_can_use_db_pool(db_pool: DBPool):
    assert isinstance(db_pool, edgedb.AsyncIOPool)
    assert await db_pool.query_single("SELECT 1") == 1


@pytest.mark.xfail(
    raises=RuntimeError,
    reason="missing 'database' marker",
    strict=True,
)
def test_can_not_use_tx_without_marker(tx):
    """Test raises RuntimError since it does not have a `database` marker."""


@pytest.mark.xfail(
    raises=RuntimeError,
    reason="has 'transaction=True' flag",
    strict=True,
)
@pytest.mark.database(transaction=True)
def test_can_not_use_tx_without_transaction_flag(tx):
    """Test raises RuntimeError since it has `transaction=True` flag."""


@pytest.mark.asyncio
@pytest.mark.database
async def test_can_use_tx(tx: DBTransaction):
    assert isinstance(tx, edgedb.AsyncIOTransaction)
    assert await tx.query_single("SELECT 1") == 1


@pytest.mark.xfail(
    raises=RuntimeError,
    reason="missing 'database' marker",
    strict=True,
)
def test_can_not_use_db_pool_or_tx(db_pool_or_tx):
    """Test raises RuntimeError since it does not have `database` marker."""


@pytest.mark.database(transaction=True)
def test_use_db_pool_or_tx_returns_db_pool(db_pool_or_tx: DBPoolOrTransaction):
    assert isinstance(db_pool_or_tx, edgedb.AsyncIOPool)


@pytest.mark.database
def test_use_db_pool_or_tx_returns_tx(db_pool_or_tx: DBPoolOrTransaction):
    assert isinstance(db_pool_or_tx, edgedb.AsyncIOTransaction)


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
