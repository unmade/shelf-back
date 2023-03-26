from __future__ import annotations

from io import BytesIO
from typing import IO, TYPE_CHECKING
from unittest import mock

import pytest
from faker import Faker

from app import security
from app.app.files.repositories import (
    IContentMetadataRepository,
    IFingerprintRepository,
    ISharedLinkRepository,
)
from app.app.services import (
    DuplicateFinderService,
    FileCoreService,
    MetadataService,
    NamespaceService,
    SharingService,
    UserService,
)
from app.infrastructure.database.edgedb import EdgeDBDatabase
from app.infrastructure.database.edgedb.db import db_context
from app.infrastructure.storage import FileSystemStorage

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Protocol

    from pytest import FixtureRequest

    from app.app.files.domain import File, Namespace
    from app.app.infrastructure import IStorage
    from app.app.users.domain import User
    from app.infrastructure.database.edgedb.typedefs import EdgeDBTransaction
    from app.typedefs import StrOrUUID

    class BookmarkFactory(Protocol):
        async def __call__(self, user_id: StrOrUUID, file_id: StrOrUUID) -> None: ...

    class FileFactory(Protocol):
        async def __call__(
            self,
            ns_path: str,
            path: str | None = None,
            content: IO[bytes] | None = None,
        ) -> File:
            ...

    class FolderFactory(Protocol):
        async def __call__(self, ns_path: str, path: str | None = None) -> File: ...

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
def _db_or_tx(request: FixtureRequest):
    """Returns regular or a transactional database instance based on database marker."""
    marker = request.node.get_closest_marker("database")
    if not marker:
        raise RuntimeError("Access to database without `database` marker!")

    if marker.kwargs.get("transaction", False):
        yield request.getfixturevalue("_database")
    else:
        yield request.getfixturevalue("_tx_database")


@pytest.fixture
def _storage(tmp_path: Path):
    """A storage instance."""
    return FileSystemStorage(tmp_path)


@pytest.fixture
def dupefinder():
    """A duplicate finder service instance."""
    database = mock.MagicMock(fingerprint=mock.AsyncMock(IFingerprintRepository))
    return DuplicateFinderService(database=database)


@pytest.fixture
def filecore(_db_or_tx: EdgeDBDatabase, _storage: IStorage):
    """A filecore service instance."""
    return FileCoreService(database=_db_or_tx, storage=_storage)


@pytest.fixture
def metadata_service():
    """A content metadata service instance."""
    database = mock.MagicMock(metadata=mock.AsyncMock(IContentMetadataRepository))
    return MetadataService(database=database)


@pytest.fixture
def namespace_service(_db_or_tx: EdgeDBDatabase):
    """A namespace service instance."""
    return NamespaceService(database=_db_or_tx)


@pytest.fixture
def sharing_service():
    """A sharing service instance."""
    database = mock.MagicMock(shared_link=mock.AsyncMock(ISharedLinkRepository))
    return SharingService(database=database)


@pytest.fixture
def user_service(_db_or_tx: EdgeDBDatabase) -> UserService:
    """A user service instance."""
    return UserService(database=_db_or_tx)


@pytest.fixture(scope="session")
def _hashed_password():
    return security.make_password("root")


@pytest.fixture
def bookmark_factory(user_service: UserService):
    """A factory to bookmark a file by ID for a given user ID."""
    async def factory(user_id: StrOrUUID, file_id: StrOrUUID) -> None:
        await user_service.add_bookmark(user_id, file_id)
    return factory


@pytest.fixture
def file_factory(filecore: FileCoreService) -> FileFactory:
    """A factory to create a File instance saved to the DB and storage."""
    async def factory(
        ns_path: str, path: str | None = None, content: IO[bytes] | None = None
    ):
        content = content or BytesIO(b"Dummy file")
        if path is None:
            path = fake.unique.file_name(category="text", extension="txt")
        return await filecore.create_file(ns_path, path, content)
    return factory


@pytest.fixture
def folder_factory(filecore: FileCoreService) -> FolderFactory:
    """A factory to create a File instance saved to the DB and storage."""
    async def factory(ns_path: str, path: str | None = None):
        if path is None:
            path = fake.unique.file_name(category="text", extension="txt")
        return await filecore.create_folder(ns_path, path)
    return factory


@pytest.fixture
async def user(_hashed_password: str, user_service: UserService) -> User:
    """A user instance."""
    # mock password hashing to speed up test setup
    with mock.patch("app.security.make_password", return_value=_hashed_password):
        return await user_service.create("admin", "root")


@pytest.fixture
async def namespace(user: User, namespace_service: NamespaceService):
    """A namespace owned by `user` fixture."""
    return await namespace_service.create(user.username, owner_id=user.id)


@pytest.fixture
async def file(namespace: Namespace, file_factory: FileFactory):
    """A file stored in the `namespace` fixture"""
    return await file_factory(namespace.path, "f.txt")


@pytest.fixture
async def folder(namespace: Namespace, folder_factory: FolderFactory):
    """A folder stored in the `namespace` fixture"""
    return await folder_factory(namespace.path, "folder")
