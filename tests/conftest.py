from __future__ import annotations

import asyncio
import contextlib
from io import BytesIO
from pathlib import Path
from typing import IO, TYPE_CHECKING, Optional, Union
from unittest import mock
from urllib.parse import urlsplit, urlunsplit

import edgedb
import pytest
from faker import Faker
from httpx import AsyncClient
from PIL import Image

from app import actions, config, crud, db, security
from app.main import create_app

if TYPE_CHECKING:
    from uuid import UUID
    from app.entities import File, User
    from app.typedefs import DBPool, StrOrPath, StrOrUUID

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


@pytest.fixture(autouse=True)
def replace_storage_root_dir_with_tmp_path(tmp_path):
    """Monkey patches storage root_dir with a temporary directory."""
    from app.storage import storage

    storage.root_dir = tmp_path


@pytest.fixture(autouse=True, scope="session")
def replace_database_dsn():
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
    with open(config.BASE_DIR / "./schema.esdl", "r") as f:
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
def file_factory(db_pool: DBPool):
    """Create dummy file, put it in a storage and save to database."""
    async def _file_factory(
        user_id: StrOrUUID,
        path: StrOrPath = None,
        content: Union[bytes, IO[bytes]] = b"I'm Dummy File!",
    ) -> File:
        path = Path(path or fake.file_name(category="text", extension="txt"))
        if isinstance(content, bytes):
            file = BytesIO(content)
        else:
            file = content  # type: ignore
        user = await crud.user.get_by_id(db_pool, user_id=user_id)
        return await actions.save_file(db_pool, user.namespace, path, file)
    return _file_factory


@pytest.fixture
def image_factory(file_factory):
    """Create dummy JPEG image file."""
    async def _image_factory(user_id: StrOrUUID, path: StrOrPath = None):
        path = Path(path or fake.file_name(category="image", extension="jpg"))
        buffer = BytesIO()
        with Image.new("RGB", (256, 256)) as im:
            im.save(buffer, "JPEG")
        buffer.seek(0)
        return await file_factory(user_id, path, content=buffer)

    return _image_factory


@pytest.fixture
def user_factory(db_pool: DBPool):
    """Create a new user, namespace, home and trash directories."""
    async def _user_factory(
        username: str = None,
        password: str = "root",
        email: Optional[str] = None,
        superuser: bool = False,
        hash_password: bool = False,
    ) -> User:
        username = username or fake.simple_profile()["username"]
        # Hashing password is an expensive operation, so do it only when need it.
        if not hash_password:
            mk_psswd = mock.patch("app.security.make_password", return_value=password)
        else:
            mk_psswd = contextlib.nullcontext()  # type: ignore

        with mk_psswd:
            await actions.create_account(
                db_pool, username, password, email=email, superuser=superuser,
            )
        query = "SELECT User { id } FILTER .username=<str>$username"
        user = await db_pool.query_one(query, username=username)
        return await crud.user.get_by_id(db_pool, user_id=user.id)

    return _user_factory


@pytest.fixture
async def user(user_factory):
    """User instance with namespace, home and trash directories."""
    return await user_factory(email=fake.email())


@pytest.fixture
async def superuser(user_factory):
    """Superuser with namespace, home and trash directories."""
    return await user_factory(email=fake.email(), superuser=True)
