from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest import mock

import pytest
from faker import Faker

from app.app.files.domain import FilePendingDeletion
from app.app.files.domain.content import InMemoryFileContent
from app.app.files.repositories import (
    IContentMetadataRepository,
    IFileMemberRepository,
    IFingerprintRepository,
    ISharedLinkRepository,
)
from app.app.files.services import (
    ContentService,
    DuplicateFinderService,
    FileMemberService,
    FileService,
    MetadataService,
    NamespaceService,
    SharingService,
    ThumbnailService,
)
from app.app.files.services.file import FileCoreService, MountService
from app.app.infrastructure import IIndexerClient, IMailBackend, IStorage, IWorker
from app.app.infrastructure.database import SENTINEL_ID
from app.app.users.repositories import IUserRepository
from app.app.users.services import BookmarkService, UserService
from app.toolkit import security
from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from typing import Protocol
    from uuid import UUID

    from app.app.files.domain import AnyPath, File, IFileContent, Namespace
    from app.app.users.domain import User
    from app.infrastructure.database.edgedb import EdgeDBDatabase
    from app.typedefs import StrOrUUID

    class BookmarkFactory(Protocol):
        async def __call__(self, user_id: StrOrUUID, file_id: UUID) -> None: ...

    class FileFactory(Protocol):
        async def __call__(
            self,
            ns_path: str,
            path: AnyPath | None = None,
            content: IFileContent | None = None,
        ) -> File:
            ...

    class FilePendingDeletionFactory(Protocol):
        async def __call__(
            self,
            ns_path: AnyPath | None = None,
            path: AnyPath | None = None,
            mediatype: str | None = None,
        ) -> FilePendingDeletion:
            ...

    class FolderFactory(Protocol):
        async def __call__(self, ns_path: str, path: AnyPath | None = None) -> File: ...

    class NamespaceFactory(Protocol):
        async def __call__(self, path: AnyPath, owner_id: UUID) -> Namespace:
            ...

    class UserFactory(Protocol):
        async def __call__(self, username: str, password: str = "root") -> User: ...


fake = Faker()


@pytest.fixture
def content_service():
    """A content service instance."""
    return ContentService(
        dupefinder=mock.MagicMock(DuplicateFinderService),
        filecore=mock.MagicMock(FileCoreService),
        indexer=mock.MagicMock(IIndexerClient),
        metadata=mock.MagicMock(MetadataService),
        thumbnailer=mock.MagicMock(ThumbnailService),
        worker=mock.MagicMock(IWorker),
    )


@pytest.fixture
def dupefinder():
    """A duplicate finder service instance."""
    database = mock.MagicMock(fingerprint=mock.AsyncMock(IFingerprintRepository))
    return DuplicateFinderService(database=database)


@pytest.fixture
def filecore(edgedb_database: EdgeDBDatabase, fs_storage: IStorage):
    """A filecore service instance."""
    worker = mock.MagicMock(IWorker)
    return FileCoreService(database=edgedb_database, storage=fs_storage, worker=worker)


@pytest.fixture
def file_service():
    """A file service instance."""
    filecore = mock.MagicMock(FileCoreService)
    mount_service = mock.MagicMock(MountService)
    return FileService(filecore=filecore, mount_service=mount_service)


@pytest.fixture
def file_member_service():
    """A file member service instance."""
    database = mock.MagicMock(
        file_member=mock.AsyncMock(IFileMemberRepository),
        user=mock.AsyncMock(IUserRepository),
    )
    return FileMemberService(database=database)


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
def thumbnailer():
    """A thumbnail service instance."""
    filecore = mock.MagicMock(FileCoreService)
    storage = mock.AsyncMock(IStorage)
    return ThumbnailService(filecore=filecore, storage=storage)


@pytest.fixture
def user_service(edgedb_database: EdgeDBDatabase):
    """A user service instance."""
    mail = mock.MagicMock(IMailBackend)
    return UserService(database=edgedb_database, mail=mail)


@pytest.fixture(scope="session")
def _hashed_password():
    return security.make_password("root")


@pytest.fixture
def bookmark_factory(edgedb_database: EdgeDBDatabase):
    """A factory to bookmark a file by ID for a given user ID."""
    bookmark_service = BookmarkService(edgedb_database)
    async def factory(user_id: UUID, file_id: UUID) -> None:
        await bookmark_service.add_bookmark(user_id, file_id)
    return factory


@pytest.fixture
def file_factory(filecore: FileCoreService) -> FileFactory:
    """A factory to create a File instance saved to the DB and storage."""
    async def factory(
        ns_path: str, path: AnyPath | None = None, content: IFileContent | None = None
    ):
        content = content or InMemoryFileContent(b"Dummy file")
        path = path or fake.unique.file_name()
        return await filecore.create_file(ns_path, path, content)
    return factory


@pytest.fixture
def file_pending_deletion_factory(
    filecore: FileCoreService
) -> FilePendingDeletionFactory:
    """A factory to create a FilePendingDeletion instance saved to the DB."""
    async def factory(
        ns_path: AnyPath | None = None,
        path: AnyPath | None = None,
        mediatype: str | None = None,
    ) -> FilePendingDeletion:
        items = await filecore.db.file_pending_deletion.save_batch([
            FilePendingDeletion(
                id=SENTINEL_ID,
                ns_path=str(ns_path) if ns_path else fake.unique.user_name(),
                path=str(path) if path else fake.unique.file_name(),
                chash=uuid.uuid4().hex,
                mediatype=mediatype or MediaType.PLAIN_TEXT,
            )
        ])
        return items[0]
    return factory


@pytest.fixture
def folder_factory(filecore: FileCoreService) -> FolderFactory:
    """A factory to create a File instance saved to the DB and storage."""
    async def factory(ns_path: str, path: AnyPath | None = None):
        path = path or fake.unique.word()
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
async def namespace_a(user_a: User, namespace_factory: NamespaceFactory):
    """A namespace owned by `user_a` fixture."""
    return await namespace_factory(user_a.username.lower(), owner_id=user_a.id)


@pytest.fixture
async def namespace_b(user_b: User, namespace_factory: NamespaceFactory):
    """A namespace owned by `user_b` fixture."""
    return await namespace_factory(user_b.username.lower(), owner_id=user_b.id)


@pytest.fixture
async def namespace(namespace_a: Namespace):
    """A namespace owned by `user` fixture."""
    return namespace_a


@pytest.fixture
async def file(namespace: Namespace, file_factory: FileFactory):
    """A file stored in the `namespace` fixture"""
    return await file_factory(namespace.path, "f.txt")


@pytest.fixture
async def folder(namespace: Namespace, folder_factory: FolderFactory):
    """A folder stored in the `namespace` fixture"""
    return await folder_factory(namespace.path, "folder")


@pytest.fixture
async def user_a(user_factory: UserFactory):
    """A User instance saved to the EdgeDB."""
    return await user_factory("admin")


@pytest.fixture
async def user_b(user_factory: UserFactory):
    """Another User instance saved to the EdgeDB."""
    return await user_factory("user_b")
