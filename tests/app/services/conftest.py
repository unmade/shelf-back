from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.app.services import NamespaceService, UserService
from app.infrastructure.database.edgedb import EdgeDBDatabase
from app.infrastructure.database.edgedb.db import db_context
from app.storage.filesystem import FileSystemStorage

if TYPE_CHECKING:
    from pathlib import Path

    from app.domain.entities import User
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
def namespace_service(tmp_path: Path, tx_database: EdgeDBDatabase) -> NamespaceService:
    return NamespaceService(database=tx_database, storage=FileSystemStorage(tmp_path))


@pytest.fixture
def user_service(tx_database: EdgeDBDatabase) -> UserService:
    return UserService(database=tx_database)


@pytest.fixture
async def user(user_service: UserService) -> User:
    return await user_service.create("admin", "root")


@pytest.fixture
async def namespace(user: User, namespace_service: NamespaceService):
    return await namespace_service.create(user.username, owner_id=user.id)
