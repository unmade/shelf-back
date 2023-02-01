from __future__ import annotations

import os.path
from typing import TYPE_CHECKING

import pytest
from faker import Faker

from app.domain.entities import SENTINEL_ID, Account, File, Namespace, User
from app.infrastructure.database.edgedb import EdgeDBDatabase
from app.infrastructure.database.edgedb.db import db_context

if TYPE_CHECKING:
    from typing import Protocol

    from app.app.repositories import (
        IAccountRepository,
        IFileRepository,
        INamespaceRepository,
        IUserRepository,
    )
    from app.infrastructure.database.edgedb.typedefs import EdgeDBTransaction

    class FileFactory(Protocol):
        async def __call__(self, ns_path: str) -> File: ...

fake = Faker()


@pytest.fixture(scope="module")
def _database(db_dsn):
    """Returns an EdgeDBDatabase instance."""
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
    """EdgeDBDatabase instance where all queries run in the same transaction."""
    # pytest-asyncio doesn't support contextvars properly, so set the context manually
    # in a regular non-async fixture.
    token = db_context.set(_tx)
    try:
        yield _database
    finally:
        db_context.reset(token)


@pytest.fixture
def account_repo(_tx_database: EdgeDBDatabase):
    """An EdgeDB instance of IAccountRepository"""
    return _tx_database.account


@pytest.fixture
def file_repo(_tx_database: EdgeDBDatabase):
    """An EdgeDB instance of IFileRepository"""
    return _tx_database.file


@pytest.fixture
def namespace_repo(_tx_database: EdgeDBDatabase):
    """An EdgeDB instance of INamespaceRepository"""
    return _tx_database.namespace


@pytest.fixture
def user_repo(_tx_database: EdgeDBDatabase):
    """An EdgeDB instance of IUserRepository"""
    return _tx_database.user


@pytest.fixture
def file_factory(file_repo: IFileRepository) -> FileFactory:
    """A Factory to create and save a File to the EdgeDB."""
    async def factory(ns_path: str):
        path = fake.unique.file_name(category="text", extension="txt")
        return await file_repo.save(
            File(
                id=SENTINEL_ID,
                ns_path=ns_path,
                name=os.path.basename(path),
                path=path,
                size=10,
                mediatype="plain/text",
            )
        )
    return factory


@pytest.fixture
async def account(user: User, account_repo: IAccountRepository):
    """An Account instance saved to the EdgeDB."""
    return await account_repo.save(
        Account(
            id=SENTINEL_ID,
            username=user.username,
            email=fake.email(),
            first_name=fake.first_name(),
            last_name=fake.last_name(),
        )
    )


@pytest.fixture
async def namespace(user: User, namespace_repo: INamespaceRepository):
    """A Namespace instance saved to the EdgeDB."""
    return await namespace_repo.save(
        Namespace(
            id=SENTINEL_ID,
            path=user.username.lower(),
            owner_id=user.id,
        )
    )


@pytest.fixture
async def file(namespace: Namespace, file_factory: FileFactory):
    """A File instance saved to the EdgeDB."""
    return await file_factory(namespace.path)


@pytest.fixture
async def user(user_repo: IUserRepository):
    """A User instance saved to the EdgeDB."""
    return await user_repo.save(
        User(
            id=SENTINEL_ID,
            username=fake.unique.user_name(),
            password=fake.password(),
            superuser=False,
        )
    )
