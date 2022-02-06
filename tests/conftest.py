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

from app import config, db, security
from app.main import create_app
from app.tasks import CeleryConfig
from tests.factories import (
    AccountFactory,
    BookmarkFactory,
    FileFactory,
    FingerprintFactory,
    MediaTypeFactory,
    NamespaceFactory,
    UserFactory,
)

if TYPE_CHECKING:
    from pathlib import Path
    from uuid import UUID

    from pytest import FixtureRequest

    from app.entities import Account, Namespace, User
    from app.typedefs import DBAnyConn, DBClient

fake = Faker()

pytest_plugins = ["pytester"]


class TestClient(AsyncClient):
    def login(self, user_id: UUID) -> TestClient:
        """
        Authenticates given user by creating access token and setting it as
        the Authorization header.
        """
        token = security.create_access_token(str(user_id))
        self.headers.update({"Authorization": f"Bearer {token}"})
        return self


def pytest_addoption(parser):
    parser.addoption(
        "--reuse-db",
        action="store_true",
        default=False,
        help=(
            "whether to keep db after the test run or drop it. "
            "If the database does not exists it will be created"
        ),
    )


@pytest.fixture(scope="session")
def reuse_db(pytestconfig):
    """
    Returns whether or not to re-use an existing database and to keep it after
    the test run.
    """
    return pytestconfig.getoption("reuse_db", False)


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
def replace_storage_location_with_tmp_path(tmp_path: Path):
    """Monkey patches storage root_dir with a temporary directory."""
    from app.storage import storage

    storage.location = str(tmp_path)


@pytest.fixture(autouse=True, scope="session")
def db_dsn() -> tuple[str, str, str]:
    """
    Parse DSN from config and return tuple:
        - first element is a DSN to server, without database name
        - second element is a DSN, but database name has suffix '_text'
        - third element is test database name (with suffix '_text')
    """
    scheme, netloc, path, query, fragments = urlsplit(config.DATABASE_DSN)
    server_dsn = urlunsplit((scheme, netloc, "", query, fragments))
    db_name = f"{path.strip('/')}_test"
    db_dsn = urlunsplit((scheme, netloc, f"/{db_name}", query, fragments))
    return server_dsn, db_dsn, db_name


@pytest.fixture(autouse=True, scope="session")
def replace_database_dsn(db_dsn):
    """Replace database DSN with a test value."""
    _, dsn, _ = db_dsn
    with mock.patch("app.config.DATABASE_DSN", dsn):
        yield


@pytest.fixture(scope="session")
def event_loop():
    """Redefine pytest-asyncio event_loop fixture with 'session' scope."""
    loop = asyncio.get_event_loop_policy().get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def setup_test_db(reuse_db, db_dsn) -> None:
    """
    Create test database and apply migration. If database already exists and
    no `--reuse-db` provided, then test database will be re-created.
    """
    server_dsn, dsn, db_name = db_dsn

    async with edgedb.create_async_client(
        dsn=server_dsn,
        max_concurrency=1,
        tls_ca_file=config.DATABASE_TLS_CA_FILE,
    ) as conn:
        should_migrate = True
        try:
            await conn.execute(f"CREATE DATABASE {db_name};")
        except edgedb.DuplicateDatabaseDefinitionError:
            if not reuse_db:
                await conn.execute(f"DROP DATABASE {db_name};")
                await conn.execute(f"CREATE DATABASE {db_name};")
            else:
                should_migrate = False

    if should_migrate:
        schema = (config.BASE_DIR / "./dbschema/default.esdl").read_text()
        async with edgedb.create_async_client(
            dsn=dsn,
            max_concurrency=1,
            tls_ca_file=config.DATABASE_TLS_CA_FILE,
        ) as conn:
            await db.migrate(conn, schema)


@pytest.fixture(scope="session")
async def session_db_client(setup_test_db):
    """A session scoped database client."""
    async with edgedb.create_async_client(
        dsn=config.DATABASE_DSN,
        max_concurrency=4,
        tls_ca_file=config.DATABASE_TLS_CA_FILE,
    ) as client:
        with mock.patch("app.db._client", client):
            yield client


@pytest.fixture
async def db_client(request: FixtureRequest, session_db_client: DBClient):
    """Yield a function-scoped database client."""
    marker = request.node.get_closest_marker("database")
    if not marker:
        raise RuntimeError("Access to database without `database` marker!")

    if not marker.kwargs.get("transaction", False):
        raise RuntimeError("Use `transaction=True` to access database client")

    yield session_db_client


@pytest.fixture
async def tx(request: FixtureRequest, session_db_client: DBClient):
    """Yield a transaction and rollback it after each test."""
    marker = request.node.get_closest_marker("database")
    if not marker:
        raise RuntimeError("Access to database without `database` marker!")

    if marker.kwargs.get("transaction", False):
        raise RuntimeError("Can't use `tx` fixture with `transaction=True` option")

    async for transaction in session_db_client.transaction():
        transaction._managed = True
        try:
            yield transaction
        finally:
            await transaction._exit(Exception, None)


@pytest.fixture
def db_client_or_tx(request: FixtureRequest):
    """
    Yield either a `tx` or a `db_client` fixture depending on `pytest.mark.database`
    params.
    """
    marker = request.node.get_closest_marker("database")
    if not marker:
        raise RuntimeError("Access to database without `database` marker!")

    if marker.kwargs.get("transaction", False):
        yield request.getfixturevalue("db_client")
    else:
        yield request.getfixturevalue("tx")


@pytest.fixture(autouse=True)
async def flush_db_if_needed(request: FixtureRequest):
    """Flush database after each tests."""
    try:
        yield
    finally:
        marker = request.node.get_closest_marker("database")
        if not marker:
            return

        if not marker.kwargs.get("transaction", False):
            return

        session_db_client: DBClient = request.getfixturevalue("session_db_client")
        await session_db_client.execute("""
            DELETE Account;
            DELETE File;
            DELETE MediaType;
            DELETE Namespace;
            DELETE User;
        """)


@pytest.fixture
def account_factory(db_client_or_tx: DBAnyConn) -> AccountFactory:
    """Create Account in the database."""
    return AccountFactory(db_client_or_tx)


@pytest.fixture
async def account(account_factory: AccountFactory) -> Account:
    """An Account instance."""
    return await account_factory(email=fake.unique.email())


@pytest.fixture
async def bookmark_factory(db_client_or_tx: DBAnyConn) -> BookmarkFactory:
    """Add file to user bookmarks."""
    return BookmarkFactory(db_client_or_tx)


@pytest.fixture
def file_factory(db_client_or_tx: DBAnyConn) -> FileFactory:
    """Create dummy file, put it in a storage and save to database."""
    return FileFactory(db_client_or_tx)


@pytest.fixture
async def fingerprint_factory(db_client_or_tx: DBAnyConn) -> FingerprintFactory:
    """Add fingerprint."""
    return FingerprintFactory(db_client_or_tx)


@pytest.fixture
def image_content() -> BytesIO:
    """Create a sample in-memory image."""
    buffer = BytesIO()
    with Image.new("RGB", (256, 256)) as im:
        im.save(buffer, "JPEG")
    buffer.seek(0)
    return buffer


@pytest.fixture
def mediatype_factory(db_client_or_tx: DBAnyConn) -> MediaTypeFactory:
    """Create a new media type."""
    return MediaTypeFactory(db_client_or_tx)


@pytest.fixture
def namespace_factory(db_client_or_tx: DBAnyConn) -> NamespaceFactory:
    """
    Create a Namespace with home and trash directories both in the database
    and in the storage.
    """
    return NamespaceFactory(db_client_or_tx)


@pytest.fixture
async def namespace(namespace_factory: NamespaceFactory) -> Namespace:
    """A Namespace instance with a home and trash directories."""
    return await namespace_factory()


@pytest.fixture
def user_factory(db_client_or_tx: DBAnyConn) -> UserFactory:
    """Create a new user in the database."""
    return UserFactory(db_client_or_tx)


@pytest.fixture
async def user(user_factory: UserFactory) -> User:
    """A User instance."""
    return await user_factory()


@pytest.fixture
async def superuser(user_factory: UserFactory) -> User:
    """A User instance as a superuser."""
    return await user_factory(superuser=True)
