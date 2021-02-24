from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock
from urllib.parse import urlsplit, urlunsplit

import edgedb
import pytest
from faker import Faker
from httpx import AsyncClient

from app import actions, config, crud, db, security
from app.main import create_app

if TYPE_CHECKING:
    from uuid import UUID
    from edgedb import AsyncIOConnection, AsyncIOPool
    from app.entities import User
    from app.typedefs import StrOrPath

fake = Faker()


class TestClient(AsyncClient):
    def login(self, user_id: UUID) -> TestClient:
        """
        Authenticates given user by creating access token and setting it as
        the Authorization header.
        """
        token = security.create_access_token(str(user_id))
        self.headers.update({"Authorization": f"Bearer {token}"})
        return self


@pytest.fixture
async def client():
    """Test client fixture to make requests against app endpoints"""
    async with TestClient(app=create_app(), base_url="http://test") as cli:
        yield cli


@pytest.fixture(autouse=True)
def replace_storage_root_dir_with_tmp_path(tmp_path):
    """Monkey patches storage root_dir with a temporary directory"""
    from app.storage import storage

    storage.root_dir = tmp_path


def _build_test_db_dsn() -> tuple[str, str, str]:
    """
    Parse DSN from config and return tuple:
        - first element is a DSN to server, without database name
        - second element is a DSN, but database name has suffix '_text'
        - third element is test database name (with suffix '_text')
    """
    scheme, netloc, path, query, fragments = urlsplit(config.EDGEDB_DSN)
    server_dsn = urlunsplit((scheme, netloc, "", query, fragments))
    db_name = f"{path.strip('/')}_test"
    db_dsn = urlunsplit((scheme, netloc, f"/{db_name}", query, fragments))
    return server_dsn, db_dsn, db_name


@pytest.fixture(scope="session")
def event_loop():
    """Redefines pytest-asyncio event_loop fixture with 'session' scope"""
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True, scope="session")
async def create_test_db() -> None:
    """
    Create test database.

    If DB already exists, then drop it first, and create again.
    """
    dsn, _, db_name = _build_test_db_dsn()
    conn = await edgedb.async_connect(dsn=dsn)
    try:
        await conn.execute(f"CREATE DATABASE {db_name};")
    except (edgedb.errors.DuplicateDatabaseDefinitionError, edgedb.errors.SchemaError):
        await conn.execute(f"DROP DATABASE {db_name};")
        await conn.execute(f"CREATE DATABASE {db_name};")
    finally:
        await conn.aclose()


@pytest.fixture(autouse=True, scope="session")
async def apply_migration(db_pool: AsyncIOPool) -> None:
    """Apply schema to test database."""
    with open(Path("./schema.esdl").resolve(), "r") as f:
        schema = f.read()

    async with db_pool.acquire() as conn:
        await db.migrate(conn, schema)


@pytest.fixture(scope="session")
async def db_pool(create_test_db):
    """Create connection pool to a database."""
    del create_test_db  # required only to preserve fixtures correct execution order

    _, dsn, _ = _build_test_db_dsn()
    async with edgedb.create_async_pool(dsn=dsn, min_size=5, max_size=5) as pool:
        with mock.patch("app.db._pool", pool):
            yield pool


@pytest.fixture
async def db_conn(apply_migration, db_pool: AsyncIOPool):
    """Acquire connection from connection pool."""
    del apply_migration  # required only to preserve fixtures correct execution order

    async with db_pool.acquire() as conn:
        try:
            yield conn
        finally:
            await conn.execute("""
                DELETE File;
                DELETE Namespace;
                DELETE User;
            """)


@pytest.fixture
async def db_conn_factory(apply_migration, db_pool: AsyncIOPool):
    """Acquire specified amount of connections and return it."""
    del apply_migration  # required only to preserve fixtures correct execution order

    connections = []

    async def wrapper(amount: int):
        nonlocal connections
        connections = await asyncio.gather(*(
            db_pool.acquire() for _ in range(amount)
        ))
        return connections

    try:
        yield wrapper
    finally:
        await asyncio.gather(*(
            db_pool.release(conn) for conn in connections
        ))


@pytest.fixture
def file_factory(db_conn: AsyncIOConnection):
    """Create dummy file, put it in a storage and save to database."""
    async def _file_factory(user_id: str, path: StrOrPath = None):
        path = Path(path or fake.file_name(category="text", extension="txt"))
        file = BytesIO(b"I'm Dummy File!")
        user = await crud.user.get_by_id(db_conn, user_id=user_id)
        return await actions.save_file(db_conn, user.namespace, path, file)
    return _file_factory


@pytest.fixture
def user_factory(db_conn: AsyncIOConnection):
    """Create a new user, namespace, home and trash directories."""
    async def _user_factory(
        username: str = None, password: str = "root", hash_password: bool = False,
    ) -> User:
        username = username or fake.simple_profile()["username"]
        # Hashing password is an expensive operation, so do it only when need it.
        if hash_password:
            await actions.create_account(db_conn, username, password)
        else:
            with mock.patch("app.security.make_password", return_value=password):
                await actions.create_account(db_conn, username, password)
        query = "SELECT User { id } FILTER .username=<str>$username"
        user = await db_conn.query_one(query, username=username)
        return await crud.user.get_by_id(db_conn, user_id=user.id)

    return _user_factory


@pytest.fixture
async def user(user_factory):
    """User instance with namespace, home and trash directories."""
    return await user_factory()
