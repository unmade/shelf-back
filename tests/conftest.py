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
    from edgedb import AsyncIOConnection, AsyncIOPool
    from app.entities import User

fake = Faker()


class TestClient(AsyncClient):
    def login(self, user_id: str) -> TestClient:
        """
        Authenticates given user by creating access token and setting it as
        the Authorization header.
        """
        token = security.create_access_token(user_id)
        self.headers.update({"Authorization": f"Bearer {token}"})
        return self


@pytest.fixture
async def client():
    """Test client fixture to make requests against app endpoints"""
    async with TestClient(app=create_app(), base_url="http://test") as cli:
        yield cli


@pytest.fixture(autouse=True)
def create_schema_for_in_memory_sqlite(request):
    """Fixture automatically creates schema when running with in-memory SQLite"""
    if config.DATABASE_DSN == "sqlite://":  # pragma: no cover
        db.Base.metadata.create_all(bind=db.engine)


@pytest.fixture(autouse=True)
def replace_storage_root_dir_with_tmp_path(tmp_path):
    """Monkey patches storage root_dir with a temporary directory"""
    from app.storage import storage

    storage.root_dir = tmp_path


@pytest.fixture
def file_factory():
    """Creates dummy file, put it in a storage and save to database."""
    def _file_factory(user_id: int, path: str = None):
        path = path or fake.file_name(category="text", extension="txt")
        with db.SessionManager() as db_session:
            file = BytesIO(b"I'm Dummy File!")
            account = crud.user.get_by_id(db_session, user_id)
            namespace = account.namespace
            result = actions.save_file(db_session, namespace, path, file)
            db_session.commit()
            return result
    return _file_factory


def _build_test_db_dsn() -> tuple[str, str, str]:
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

    If DB already exists, then drop it first.
    """
    dsn, _, db_name = _build_test_db_dsn()
    conn = await edgedb.async_connect(dsn=dsn)
    try:
        await conn.execute(f"CREATE DATABASE {db_name}")
    except edgedb.errors.SchemaError:
        await conn.execute(f"DROP DATABASE {db_name}")
        await conn.execute(f"CREATE DATABASE {db_name}")
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
async def db_pool(create_test_db) -> None:
    """Create connection pool to a database."""
    del create_test_db  # required only to preserve fixtures correct execution order

    _, dsn, _ = _build_test_db_dsn()
    async with edgedb.create_async_pool(dsn=dsn, min_size=5, max_size=5) as pool:
        with mock.patch("app.db._pool", pool):
            yield pool


@pytest.fixture
async def db_conn(apply_migration, db_pool: AsyncIOPool):
    """Return connection from connection pool."""
    del apply_migration  # required only to preserve fixtures correct execution order

    async with db_pool.acquire() as conn:
        try:
            yield conn
        finally:
            await conn.execute("DELETE File")
            await conn.execute("DELETE Namespace")
            await conn.execute("DELETE User")


@pytest.fixture
def user_factory(db_conn: AsyncIOConnection):
    """Creates a new user, namespace, home and trash directories."""
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
        user = await crud.user.get_by_username(db_conn, username=username)
        return await crud.user.get_by_id(db_conn, user_id=user.id)

    return _user_factory
