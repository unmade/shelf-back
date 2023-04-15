from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from faker import Faker

from app.app.files.domain import (
    ContentMetadata,
    Exif,
    File,
    Fingerprint,
    Namespace,
    Path,
    SharedLink,
    mediatypes,
)
from app.app.infrastructure.database import SENTINEL_ID
from app.app.users.domain import (
    Account,
    User,
)
from app.app.users.domain.bookmark import Bookmark

if TYPE_CHECKING:
    from typing import Protocol

    from app.app.files.domain import AnyPath
    from app.app.files.repositories import (
        IContentMetadataRepository,
        IFileRepository,
        IFingerprintRepository,
        INamespaceRepository,
        ISharedLinkRepository,
    )
    from app.app.users.repositories import (
        IAccountRepository,
        IBookmarkRepository,
        IUserRepository,
    )
    from app.infrastructure.database.edgedb import EdgeDBDatabase

    class FileFactory(Protocol):
        async def __call__(
            self,
            ns_path: str,
            path: AnyPath | None = None,
            mediatype: str = "plain/text",
        ) -> File:
            ...

    class FingerprintFactory(Protocol):
        async def __call__(self, file_id: str, value: int) -> Fingerprint: ...

    class FolderFactory(Protocol):
        async def __call__(self, ns_path: str, path: AnyPath | None = None) -> File: ...

    class SharedLinkFactory(Protocol):
        async def __call__(self, file_id: str) -> SharedLink: ...

fake = Faker()


@pytest.fixture
def account_repo(edgedb_database: EdgeDBDatabase):
    """An EdgeDB instance of IAccountRepository"""
    return edgedb_database.account


@pytest.fixture
def audit_trail_repo(edgedb_database: EdgeDBDatabase):
    """An EdgeDB instance of IAuditTrailRepository"""
    return edgedb_database.audit_trail


@pytest.fixture
def bookmark_repo(edgedb_database: EdgeDBDatabase):
    """An EdgeDB instance of IBookmarkRepository"""
    return edgedb_database.bookmark


@pytest.fixture
def file_repo(edgedb_database: EdgeDBDatabase):
    """An EdgeDB instance of IFileRepository"""
    return edgedb_database.file


@pytest.fixture
def fingerprint_repo(edgedb_database: EdgeDBDatabase):
    """An EdgeDB instance of IFingerprintRepository"""
    return edgedb_database.fingerprint


@pytest.fixture
def metadata_repo(edgedb_database: EdgeDBDatabase):
    """An EdgeDB instance of IContentMetadataRepository"""
    return edgedb_database.metadata


@pytest.fixture
def namespace_repo(edgedb_database: EdgeDBDatabase):
    """An EdgeDB instance of INamespaceRepository"""
    return edgedb_database.namespace


@pytest.fixture
def shared_link_repo(edgedb_database: EdgeDBDatabase):
    """An EdgeDB instance of ISharedLinkRepository"""
    return edgedb_database.shared_link


@pytest.fixture
def user_repo(edgedb_database: EdgeDBDatabase):
    """An EdgeDB instance of IUserRepository"""
    return edgedb_database.user


@pytest.fixture
def file_factory(file_repo: IFileRepository) -> FileFactory:
    """A factory to create a saved File to the EdgeDB."""
    async def factory(
        ns_path: str, path: AnyPath | None = None, mediatype: str = "plain/text"
    ):
        if path is None:
            path = fake.unique.file_name(category="text", extension="txt")
        return await file_repo.save(
            File(
                id=SENTINEL_ID,
                ns_path=ns_path,
                name=Path(path).name,
                path=path,
                size=10,
                mediatype=mediatype,
            )
        )
    return factory


@pytest.fixture
def fingerprint_factory(fingerprint_repo: IFingerprintRepository) -> FingerprintFactory:
    async def factory(file_id: str, value: int):
        return await fingerprint_repo.save(
            Fingerprint(file_id, value=value)
        )
    return factory


@pytest.fixture
def folder_factory(file_repo: IFileRepository) -> FolderFactory:
    """A factory to create a saved Folder to the EdgeDB."""
    async def factory(ns_path: str, path: AnyPath | None = None):
        path = path or fake.unique.file_name(category="text", extension="txt")
        return await file_repo.save(
            File(
                id=SENTINEL_ID,
                ns_path=ns_path,
                name=Path(path).name,
                path=path,
                size=0,
                mediatype=mediatypes.FOLDER,
            )
        )
    return factory


@pytest.fixture
async def account(user: User, account_repo: IAccountRepository):
    """An Account instance saved to the EdgeDB."""
    return await account_repo.save(
        Account(
            id=SENTINEL_ID,
            username=user.username,
            email=fake.email(),
            first_name=fake.first_name(),
            last_name=fake.last_name(),
        )
    )


@pytest.fixture
async def namespace(user: User, namespace_repo: INamespaceRepository):
    """A Namespace instance saved to the EdgeDB."""
    return await namespace_repo.save(
        Namespace(
            id=SENTINEL_ID,
            path=user.username.lower(),
            owner_id=user.id,
        )
    )


@pytest.fixture
async def file(namespace: Namespace, file_factory: FileFactory):
    """A File instance saved to the EdgeDB."""
    return await file_factory(namespace.path)


@pytest.fixture
async def shared_link(shared_link_repo: ISharedLinkRepository, file: File):
    """A SharedLink instance saved to the EdgeDB."""
    return await shared_link_repo.save(
        SharedLink(
            id=SENTINEL_ID,
            file_id=file.id,
            token="ec67376f",
        )
    )


@pytest.fixture
async def content_metadata(metadata_repo: IContentMetadataRepository, file: File):
    """A ContentMetadata instance saved to the EdgeDB."""
    exif = Exif(width=1280, height=800)
    return await metadata_repo.save(
        ContentMetadata(
            file_id=file.id,
            data=exif,
        )
    )


@pytest.fixture
async def user(user_repo: IUserRepository):
    """A User instance saved to the EdgeDB."""
    return await user_repo.save(
        User(
            id=SENTINEL_ID,
            username=fake.unique.user_name(),
            password=fake.password(),
            superuser=False,
        )
    )


@pytest.fixture
async def bookmark(bookmark_repo: IBookmarkRepository, file: File, user: User):
    bookmark = Bookmark(user_id=str(user.id), file_id=file.id)
    return await bookmark_repo.save(bookmark)
