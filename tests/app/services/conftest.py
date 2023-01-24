from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

from app.app.services import NamespaceService, UserService
from app.infrastructure.database.edgedb import EdgeDBDatabase
from app.infrastructure.database.edgedb.db import db_context
from app.storage.filesystem import FileSystemStorage

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import FixtureRequest

    from app.domain.entities import User
    from app.infrastructure.database.edgedb.typedefs import EdgeDBTransaction


@pytest.fixture(scope="module")
def _database(db_dsn):
    """Returns a database instance."""
    _, dsn, _ = db_dsn
    return EdgeDBDatabase(
        dsn,
        max_concurrency=1,
        tls_security="insecure"
    )


@pytest.fixture
async def _tx(_database: EdgeDBDatabase):
    """Yields a transaction and rollback it after each test."""
    async for transaction in _database.client.transaction():
        transaction._managed = True
        try:
            yield transaction
        finally:
            await transaction._exit(Exception, None)


@pytest.fixture
def _tx_database(_database: EdgeDBDatabase, _tx: EdgeDBTransaction):
    """Database instance where all queries run in the same transaction."""
    # pytest-asyncio doesn't support contextvars properly, so set the context manually
    # in a regular non-async fixture.
    token = db_context.set(_tx)
    try:
        yield _database
    finally:
        db_context.reset(token)


@pytest.fixture
def _db_or_tx(request: FixtureRequest):
    """Returns regular or a transactional database instance based on database marker."""
    marker = request.node.get_closest_marker("database")
    if not marker:
        raise RuntimeError("Access to database without `database` marker!")

    if marker.kwargs.get("transaction", False):
        yield request.getfixturevalue("_database")
    else:
        yield request.getfixturevalue("_tx_database")


@pytest.fixture
def namespace_service(_db_or_tx, tmp_path: Path):
    """A namespace service instance."""
    storage = FileSystemStorage(tmp_path)
    return NamespaceService(database=_db_or_tx, storage=storage)


@pytest.fixture
def user_service(_db_or_tx: EdgeDBDatabase) -> UserService:
    """A user service instance."""
    return UserService(database=_db_or_tx)


@pytest.fixture
async def user(user_service: UserService) -> User:
    """A user instance."""
    # mock password hashing to speed up test setup
    with mock.patch("app.security.make_password", return_value="root"):
        return await user_service.create("admin", "root")


@pytest.fixture
async def namespace(user: User, namespace_service: NamespaceService):
    """A namespace owned by `user` fixture."""
    return await namespace_service.create(user.username, owner_id=user.id)
