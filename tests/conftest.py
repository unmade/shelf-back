from __future__ import annotations

import asyncio
from io import BytesIO
from typing import TYPE_CHECKING
from unittest import mock
from urllib.parse import urlsplit, urlunsplit

import edgedb
import pytest
from faker import Faker
from httpx import AsyncClient
from PIL import Image
from tests import factories

from app import config, db, security
from app.main import create_app
from app.tasks import CeleryConfig

if TYPE_CHECKING:
    from uuid import UUID
    from app.entities import Account, Namespace, User
    from app.typedefs import DBPool

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
def app():
    """Application fixture."""
    return create_app()


@pytest.fixture
async def client(app):
    """Test client fixture to make requests against app endpoints."""
    async with TestClient(app=app, base_url="http://test") as cli:
        yield cli


@pytest.fixture(scope='session')
def celery_config():
    return {
        "broker_url": CeleryConfig.broker_url,
        "result_backend": CeleryConfig.result_backend,
        "result_serializer": CeleryConfig.result_serializer,
        "event_serializer": CeleryConfig.event_serializer,
        "accept_content": CeleryConfig.accept_content,
        "result_accept_content": CeleryConfig.result_accept_content,
    }


@pytest.fixture(autouse=True)
def replace_storage_location_with_tmp_path(tmp_path):
    """Monkey patches storage root_dir with a temporary directory."""
    from app.storage import storage

    storage.location = tmp_path


@pytest.fixture(autouse=True, scope="session")
def replace_database_dsn():
    """Replace database DSN with a test value."""
    _, dsn, _ = _build_test_db_dsn()
    with mock.patch("app.config.EDGEDB_DSN", dsn):
        yield


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
    """Redefines pytest-asyncio event_loop fixture with 'session' scope."""
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


@pytest.fixture(scope="session")
async def create_db_pool(create_test_db):
    """Create connection pool to a database."""
    del create_test_db  # required only to preserve fixtures correct execution order

    _, dsn, _ = _build_test_db_dsn()
    async with edgedb.create_async_pool(dsn=dsn, min_size=3, max_size=3) as pool:
        with mock.patch("app.db._pool", pool):
            yield pool


@pytest.fixture(autouse=True, scope="session")
async def apply_migration(create_db_pool: DBPool) -> None:
    """Apply schema to test database."""
    with open(config.BASE_DIR / "./dbschema/default.esdl", "r") as f:
        schema = f.read()

    await db.migrate(create_db_pool, schema)


@pytest.fixture
async def db_pool(create_db_pool):
    """Yields database pool and delete tables on teardown."""
    yield create_db_pool


@pytest.fixture(autouse=True)
async def cleanup_tables(db_pool):
    """Clean up tables after each test."""
    try:
        yield
    finally:
        await db_pool.execute("""
            DELETE File;
            DELETE Namespace;
            DELETE User;
        """)


@pytest.fixture
def account_factory(db_pool: DBPool) -> factories.AccountFactory:
    """Create Account in the database."""
    return factories.AccountFactory(db_pool)


@pytest.fixture
async def account(account_factory: factories.AccountFactory) -> Account:
    """An Account instance."""
    return await account_factory(email=fake.email())


@pytest.fixture
def file_factory(db_pool: DBPool) -> factories.FileFactory:
    """Create dummy file, put it in a storage and save to database."""
    return factories.FileFactory(db_pool)


@pytest.fixture
def image_content() -> BytesIO:
    """Create a sample in-memory image."""
    buffer = BytesIO()
    with Image.new("RGB", (256, 256)) as im:
        im.save(buffer, "JPEG")
    buffer.seek(0)
    return buffer


@pytest.fixture
def namespace_factory(db_pool: DBPool) -> factories.NamespaceFactory:
    """
    Create a Namespace with home and trash directories both in the database
    and in the storage.
    """
    return factories.NamespaceFactory(db_pool)


@pytest.fixture
async def namespace(namespace_factory: factories.NamespaceFactory) -> Namespace:
    """A Namespace instance with a home and trash directories."""
    return await namespace_factory()


@pytest.fixture
def user_factory(db_pool: DBPool) -> factories.UserFactory:
    """Create a new user in the database."""
    return factories.UserFactory(db_pool)


@pytest.fixture
async def user(user_factory: factories.UserFactory) -> User:
    """A User instance."""
    return await user_factory()


@pytest.fixture
async def superuser(user_factory: factories.UserFactory) -> User:
    """A User instance as a superuser."""
    return await user_factory(superuser=True)
