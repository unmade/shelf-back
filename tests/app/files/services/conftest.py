from __future__ import annotations

from io import BytesIO
from typing import IO, TYPE_CHECKING
from unittest import mock

import pytest
from faker import Faker

from app.app.files.repositories import (
    IContentMetadataRepository,
    IFingerprintRepository,
    ISharedLinkRepository,
)
from app.app.files.services import (
    DuplicateFinderService,
    FileService,
    MetadataService,
    NamespaceService,
    SharingService,
)
from app.app.files.services.file import FileCoreService, MountService
from app.app.users.services import BookmarkService, UserService
from app.toolkit import security

if TYPE_CHECKING:
    from typing import Protocol
    from uuid import UUID

    from app.app.files.domain import AnyPath, File, Namespace
    from app.app.infrastructure import IStorage
    from app.app.users.domain import User
    from app.infrastructure.database.edgedb import EdgeDBDatabase
    from app.typedefs import StrOrUUID

    class BookmarkFactory(Protocol):
        async def __call__(self, user_id: StrOrUUID, file_id: StrOrUUID) -> None: ...

    class FileFactory(Protocol):
        async def __call__(
            self,
            ns_path: str,
            path: str,
            content: IO[bytes] | None = None,
        ) -> File:
            ...

    class FolderFactory(Protocol):
        async def __call__(self, ns_path: str, path: str) -> File: ...

    class NamespaceFactory(Protocol):
        async def __call__(self, path: AnyPath, owner_id: UUID) -> Namespace:
            ...

    class UserFactory(Protocol):
        async def __call__(self, username: str, password: str = "root") -> User: ...


fake = Faker()


@pytest.fixture
def dupefinder():
    """A duplicate finder service instance."""
    database = mock.MagicMock(fingerprint=mock.AsyncMock(IFingerprintRepository))
    return DuplicateFinderService(database=database)


@pytest.fixture
def filecore(edgedb_database: EdgeDBDatabase, fs_storage: IStorage):
    """A filecore service instance."""
    return FileCoreService(database=edgedb_database, storage=fs_storage)


@pytest.fixture
def file_service():
    """A file service instance."""
    filecore = mock.MagicMock(FileCoreService)
    mount_service = mock.MagicMock(MountService)
    return FileService(filecore=filecore, mount_service=mount_service)


@pytest.fixture
def metadata_service():
    """A content metadata service instance."""
    database = mock.MagicMock(metadata=mock.AsyncMock(IContentMetadataRepository))
    return MetadataService(database=database)


@pytest.fixture
def namespace_service(edgedb_database: EdgeDBDatabase, filecore: FileCoreService):
    """A namespace service instance."""
    return NamespaceService(database=edgedb_database, filecore=filecore)


@pytest.fixture
def sharing_service():
    """A sharing service instance."""
    database = mock.MagicMock(shared_link=mock.AsyncMock(ISharedLinkRepository))
    return SharingService(database=database)


@pytest.fixture
def user_service(edgedb_database: EdgeDBDatabase):
    """A user service instance."""
    from app.app.users.services import UserService

    return UserService(database=edgedb_database)


@pytest.fixture(scope="session")
def _hashed_password():
    return security.make_password("root")


@pytest.fixture
def bookmark_factory(edgedb_database: EdgeDBDatabase):
    """A factory to bookmark a file by ID for a given user ID."""
    bookmark_service = BookmarkService(edgedb_database)
    async def factory(user_id: StrOrUUID, file_id: StrOrUUID) -> None:
        await bookmark_service.add_bookmark(user_id, str(file_id))
    return factory


@pytest.fixture
def file_factory(filecore: FileCoreService) -> FileFactory:
    """A factory to create a File instance saved to the DB and storage."""
    async def factory(
        ns_path: str, path: str, content: IO[bytes] | None = None
    ):
        content = content or BytesIO(b"Dummy file")
        return await filecore.create_file(ns_path, path, content)
    return factory


@pytest.fixture
def folder_factory(filecore: FileCoreService) -> FolderFactory:
    """A factory to create a File instance saved to the DB and storage."""
    async def factory(ns_path: str, path: str):
        return await filecore.create_folder(ns_path, path)
    return factory


@pytest.fixture
def namespace_factory(namespace_service: NamespaceService) -> NamespaceFactory:
    """A factory to create a Namespace instance saved to the DB."""
    async def factory(path: AnyPath, owner_id: UUID) -> Namespace:
        return await namespace_service.create(path, owner_id)
    return factory


@pytest.fixture
def user_factory(user_service: UserService, _hashed_password: str) -> UserFactory:
    """A factory to create a User instance saved to the DB."""
    async def factory(username: str, password: str = "root") -> User:
        # mock password hashing to speed up test setup
        target = "app.app.users.services.user.security.make_password"
        with mock.patch(target, return_value=_hashed_password):
            return await user_service.create(username, password)
    return factory


@pytest.fixture
async def namespace(namespace_factory: NamespaceFactory, user: User):
    """A namespace owned by `user` fixture."""
    return await namespace_factory(user.username, owner_id=user.id)


@pytest.fixture
async def file(namespace: Namespace, file_factory: FileFactory):
    """A file stored in the `namespace` fixture"""
    return await file_factory(namespace.path, "f.txt")


@pytest.fixture
async def folder(namespace: Namespace, folder_factory: FolderFactory):
    """A folder stored in the `namespace` fixture"""
    return await folder_factory(namespace.path, "folder")


@pytest.fixture
async def user(user_factory: UserFactory) -> User:
    """A user instance."""
    return await user_factory("admin")
