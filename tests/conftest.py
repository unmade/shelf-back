from __future__ import annotations

import asyncio
import time
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

from app import actions, config, crud, db, mediatypes, security
from app.entities import Account, User
from app.main import create_app
from app.storage import storage
from app.tasks import CeleryConfig

if TYPE_CHECKING:
    from uuid import UUID
    from app.entities import File, Namespace
    from app.typedefs import DBPool, StrOrPath

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
def account_factory(db_pool: DBPool, user_factory):
    """Create Account in the database."""
    async def _account_factory(
        email: Optional[str] = None,
        first_name: str = "",
        last_name: str = "",
        user: Optional[User] = None
    ) -> Account:
        if user is None:
            user = await user_factory()

        query = """
            SELECT (
                INSERT Account {
                    email := <OPTIONAL str>$email,
                    first_name := <str>$first_name,
                    last_name := <str>$last_name,
                    user := (
                        SELECT
                            User
                        FILTER
                            .id = <uuid>$user_id
                    )
                }
            ) { id, email, first_name, last_name, user: { username, superuser } }
        """

        return Account.from_db(
            await db_pool.query_one(
                query,
                email=email,
                user_id=user.id,
                first_name=first_name,
                last_name=last_name,
            )
        )

    return _account_factory


@pytest.fixture
async def account(account_factory):
    """An Account instance."""
    return await account_factory(email=fake.email())


@pytest.fixture
def namespace_factory(db_pool: DBPool, user_factory):
    """
    Create a Namespace with home and trash directories both in the database
    and in the storage.
    """
    async def _namespace_factory(owner: Optional[User] = None) -> Namespace:
        if owner is None:
            owner = await user_factory()

        namespace = crud.namespace.namespace_from_db(
            await db_pool.query_one("""
                SELECT (
                    INSERT Namespace {
                        path := <str>$path,
                        owner := (
                            SELECT
                                User
                            FILTER
                                .id = <uuid>$owner_id
                        )
                    }
                ) { id, path, owner: { id, username, superuser } }
            """, path=owner.username, owner_id=owner.id)
        )

        query = """
            WITH
               Parent := File
            SELECT (
                INSERT File {
                    name := <str>$name,
                    path := <str>$path,
                    size := 0,
                    mtime := <float64>$mtime,
                    mediatype := (
                        INSERT MediaType {
                            name := <str>$mediatype
                        }
                        UNLESS CONFLICT ON .name
                        ELSE (
                            SELECT
                                MediaType
                            FILTER
                                .name = <str>$mediatype
                        )
                    ),
                    parent := (
                        SELECT
                            Parent
                        FILTER
                            .id = <OPTIONAL uuid>$parent_id
                        LIMIT 1
                    ),
                    namespace := (
                        SELECT
                            Namespace
                        FILTER
                            .id = <uuid>$namespace_id
                    )
                }
            ) { id }
        """

        home = await db_pool.query_one(
            query,
            name=str(namespace.path),
            path=".",
            mtime=time.time(),
            mediatype=mediatypes.FOLDER,
            parent_id=None,
            namespace_id=namespace.id,
        )

        await db_pool.query_one(
            query,
            name=config.TRASH_FOLDER_NAME,
            path=config.TRASH_FOLDER_NAME,
            mtime=time.time(),
            mediatype=mediatypes.FOLDER,
            parent_id=home.id,
            namespace_id=namespace.id,
        )

        await storage.makedirs(namespace.path)
        await storage.makedirs(namespace.path / config.TRASH_FOLDER_NAME)

        return namespace

    return _namespace_factory


@pytest.fixture
async def namespace(namespace_factory):
    """A Namespace instance with a home and trash directories."""
    return await namespace_factory()


@pytest.fixture
def file_factory(db_pool: DBPool):
    """Create dummy file, put it in a storage and save to database."""
    async def _file_factory(
        ns_path: StrOrPath,
        path: StrOrPath = None,
        content: Union[bytes, IO[bytes]] = b"I'm Dummy File!",
    ) -> File:
        path = Path(path or fake.file_name(category="text", extension="txt"))
        if isinstance(content, bytes):
            file = BytesIO(content)
        else:
            file = content  # type: ignore
        namespace = await crud.namespace.get(db_pool, ns_path)
        return await actions.save_file(db_pool, namespace, path, file)
    return _file_factory


@pytest.fixture
def image_content():
    """Create a sample in-memory image."""
    buffer = BytesIO()
    with Image.new("RGB", (256, 256)) as im:
        im.save(buffer, "JPEG")
    buffer.seek(0)
    return buffer


@pytest.fixture
def image_factory(file_factory, image_content):
    """Create dummy JPEG image file."""
    async def _image_factory(ns_path: StrOrPath, path: StrOrPath = None):
        path = Path(path or fake.file_name(category="image", extension="jpg"))
        return await file_factory(ns_path, path, content=image_content)

    return _image_factory


@pytest.fixture
def user_factory(db_pool: DBPool):
    """Create a new user in the database."""
    async def _user_factory(
        username: str = None,
        password: str = "root",
        superuser: bool = False,
        hash_password: bool = False,
    ) -> User:
        username = username or fake.simple_profile()["username"]
        if hash_password:
            password = security.make_password(password)

        # TODO: create user with plain query, cause crud.user.create do too much stuff
        return User.from_orm(
            await db_pool.query_one("""
                SELECT (
                    INSERT User {
                        username := <str>$username,
                        password := <str>$password,
                        superuser := <bool>$superuser,
                    }
                ) { id, username, superuser }
            """, username=username, password=password, superuser=superuser)
        )

    return _user_factory


@pytest.fixture
async def user(user_factory):
    """A User instance."""
    return await user_factory()


@pytest.fixture
async def superuser(user_factory):
    """A User instance as a superuser."""
    return await user_factory(superuser=True)
