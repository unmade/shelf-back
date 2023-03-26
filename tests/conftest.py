from __future__ import annotations

import asyncio
from importlib import resources
from io import BytesIO
from typing import TYPE_CHECKING
from unittest import mock
from urllib.parse import urlsplit, urlunsplit

import edgedb
import pytest
from faker import Faker
from PIL import Image

from app import config, db
from app.infrastructure.database.edgedb import EdgeDBDatabase
from app.tasks import CeleryConfig

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import FixtureRequest

fake = Faker()

pytest_plugins = ["pytester"]


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
    from app.infrastructure.storage import storage

    storage.location = str(tmp_path)
    with mock.patch("app.config.STORAGE_LOCATION", tmp_path):
        yield


@pytest.fixture(autouse=True, scope="session")
def db_dsn() -> tuple[str, str, str]:
    """
    Parse DSN from config and return tuple:
        - first element is a DSN to server, without database name
        - second element is a DSN, but database name has suffix '_text'
        - third element is test database name (with suffix '_text')
    """
    assert config.DATABASE_DSN is not None
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
        tls_security=config.DATABASE_TLS_SECURITY,
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
            tls_security=config.DATABASE_TLS_SECURITY,
        ) as conn:
            await db.migrate(conn, schema)


@pytest.fixture(scope="session")
async def session_db_client(setup_test_db):
    """A session scoped database client."""
    database = EdgeDBDatabase(
        dsn=config.DATABASE_DSN,
        max_concurrency=4,
        tls_ca_file=config.DATABASE_TLS_CA_FILE,
        tls_security=config.DATABASE_TLS_SECURITY,
    )
    with mock.patch("app.main._create_database", return_value=database):
        yield database.client


@pytest.fixture(scope="session")
def session_sync_client(setup_test_db):
    with edgedb.create_client(
        dsn=config.DATABASE_DSN,
        max_concurrency=1,
        tls_ca_file=config.DATABASE_TLS_CA_FILE,
        tls_security=config.DATABASE_TLS_SECURITY,
    ) as client:
        yield client


@pytest.fixture(autouse=True)
def flush_db_if_needed(request: FixtureRequest):
    """Flush database after each tests."""
    try:
        yield
    finally:
        if marker := request.node.get_closest_marker("database"):
            if marker.kwargs.get("transaction", False):
                session_db_client = request.getfixturevalue("session_sync_client")
                session_db_client.execute("""
                    DELETE Account;
                    DELETE File;
                    DELETE FileMetadata;
                    DELETE Fingerprint;
                    DELETE MediaType;
                    DELETE Namespace;
                    DELETE SharedLink;
                    DELETE User;
                """)


@pytest.fixture
def image_content() -> BytesIO:
    """Create a sample in-memory image."""
    buffer = BytesIO()
    with Image.new("RGB", (256, 256)) as im:
        im.save(buffer, "JPEG")
    buffer.seek(0)
    return buffer


@pytest.fixture
def image_content_with_exif() -> BytesIO:
    name = "exif_iphone_with_hdr_on.jpeg"
    return BytesIO(resources.files("tests.data.images").joinpath(name).read_bytes())
