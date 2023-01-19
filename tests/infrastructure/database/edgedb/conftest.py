from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.infrastructure.database.edgedb import EdgeDBDatabase
from app.infrastructure.database.edgedb.db import db_context

if TYPE_CHECKING:
    from app.infrastructure.database.edgedb.typedefs import EdgeDBTransaction


@pytest.fixture(scope="module")
def database(db_dsn):
    _, dsn, _ = db_dsn
    return EdgeDBDatabase(
        dsn,
        max_concurrency=1,
        tls_security="insecure"
    )


@pytest.fixture
async def tx(database: EdgeDBDatabase):
    async for transaction in database.client.transaction():
        transaction._managed = True
        try:
            yield transaction
        finally:
            await transaction._exit(Exception, None)


@pytest.fixture
def tx_database(database: EdgeDBDatabase, tx: EdgeDBTransaction):
    token = db_context.set(tx)
    try:
        yield database
    finally:
        db_context.reset(token)


@pytest.fixture
def user_repo(tx_database: EdgeDBDatabase):
    return tx_database.user
