from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from faker import Faker

from app.app.repositories import IAccountRepository, IUserRepository
from app.domain.entities import SENTINEL_ID, Account, User
from app.infrastructure.database.edgedb import EdgeDBDatabase
from app.infrastructure.database.edgedb.db import db_context

if TYPE_CHECKING:
    from app.infrastructure.database.edgedb.typedefs import EdgeDBTransaction

fake = Faker()


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
def file_repo(tx_database: EdgeDBDatabase):
    return tx_database.file


@pytest.fixture
def account_repo(tx_database: EdgeDBDatabase):
    return tx_database.account


@pytest.fixture
def namespace_repo(tx_database: EdgeDBDatabase):
    return tx_database.namespace


@pytest.fixture
def user_repo(tx_database: EdgeDBDatabase):
    return tx_database.user


@pytest.fixture
async def account(user: User, account_repo: IAccountRepository):
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
async def user(user_repo: IUserRepository):
    return await user_repo.save(
        User(
            id=SENTINEL_ID,
            username=fake.unique.user_name(),
            password=fake.password(),
            superuser=False,
        )
    )
