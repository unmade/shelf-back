from __future__ import annotations

import os.path
import uuid
from typing import TYPE_CHECKING

import pytest
from faker import Faker

from app.app.files.domain import (
    ContentMetadata,
    Exif,
    File,
    FileMember,
    Fingerprint,
    MountPoint,
    Namespace,
    Path,
    SharedLink,
    mediatypes,
)
from app.app.files.repositories import IFileMemberRepository
from app.app.infrastructure.database import SENTINEL_ID
from app.app.photos.domain import MediaItem
from app.app.photos.domain.media_item import IMediaItemType
from app.app.users.domain import (
    Account,
    User,
)
from app.app.users.domain.bookmark import Bookmark
from app.config import config
from app.toolkit.mediatypes import MediaType

if TYPE_CHECKING:
    from typing import Protocol
    from uuid import UUID

    from app.app.files.domain import AnyPath
    from app.app.files.repositories import (
        IContentMetadataRepository,
        IFileRepository,
        IFingerprintRepository,
        IMountRepository,
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

    class FileMemberFactory(Protocol):
        async def __call__(self, file_id: UUID, user_id: UUID) -> FileMember: ...

    class FingerprintFactory(Protocol):
        async def __call__(self, file_id: UUID, value: int) -> Fingerprint: ...

    class FolderFactory(Protocol):
        async def __call__(self, ns_path: str, path: AnyPath | None = None) -> File:
            ...

    class MediaItemFactory(Protocol):
        async def __call__(
            self,
            user_id: UUID,
            name: str | None = None,
            mediatype: IMediaItemType = MediaType.IMAGE_JPEG,
        ) -> MediaItem:
            ...

    class MountFactory(Protocol):
        async def __call__(
            self,
            source_file_id: UUID,
            target_folder_id: UUID,
            display_name: str,
        ) -> MountPoint:
            ...

    class NamespaceFactory(Protocol):
        async def __call__(self, path: AnyPath, owner_id: UUID) -> Namespace:
            ...

    class SharedLinkFactory(Protocol):
        async def __call__(self, file_id: UUID) -> SharedLink:
            ...

    class UserFactory(Protocol):
        async def __call__(
            self, username: str | None = None, password: str | None = None
        ) -> User:
            ...

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
def file_member_repo(edgedb_database: EdgeDBDatabase):
    """An EdgeDB instance of IFileMemberRepository"""
    return edgedb_database.file_member


@pytest.fixture
def fingerprint_repo(edgedb_database: EdgeDBDatabase):
    """An EdgeDB instance of IFingerprintRepository"""
    return edgedb_database.fingerprint


@pytest.fixture
def media_item_repo(edgedb_database: EdgeDBDatabase):
    """An EdgeDB instance of IMediaTypeRepository"""
    return edgedb_database.media_item


@pytest.fixture
def metadata_repo(edgedb_database: EdgeDBDatabase):
    """An EdgeDB instance of IContentMetadataRepository"""
    return edgedb_database.metadata


@pytest.fixture
async def mount_repo(edgedb_database: EdgeDBDatabase):
    """An EdgeDB instance of IMountRepository"""
    return edgedb_database.mount


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
                path=Path(path),
                size=10,
                mediatype=mediatype,
            )
        )
    return factory


@pytest.fixture
def file_member_factory(file_member_repo: IFileMemberRepository) -> FileMemberFactory:
    async def factory(file_id: UUID, user_id: UUID) -> FileMember:
        return await file_member_repo.save(
            FileMember(
                file_id=file_id,
                actions=FileMember.EDITOR,
                user=FileMember.User(
                    id=user_id,
                    username="",
                ),
            )
        )
    return factory


@pytest.fixture
def fingerprint_factory(fingerprint_repo: IFingerprintRepository) -> FingerprintFactory:
    async def factory(file_id: UUID, value: int):
        return await fingerprint_repo.save(
            Fingerprint(file_id, value=value)
        )
    return factory


@pytest.fixture
def folder_factory(file_repo: IFileRepository) -> FolderFactory:
    """A factory to create a saved Folder to the EdgeDB."""
    async def factory(ns_path: str, path: AnyPath | None = None):
        path = path or fake.unique.word()
        return await file_repo.save(
            File(
                id=SENTINEL_ID,
                ns_path=ns_path,
                name=Path(path).name,
                path=Path(path),
                size=0,
                mediatype=mediatypes.FOLDER,
            )
        )
    return factory


@pytest.fixture
def media_item_factory(
    namespace_repo: INamespaceRepository, file_factory: FileFactory,
) -> MediaItemFactory:
    """A factory to create a saved MediaItem to the EdgeDB."""
    async def factory(
        user_id: UUID,
        name: str | None = None,
        mediatype: IMediaItemType = MediaType.IMAGE_JPEG,
    ) -> MediaItem:
        namespace = await namespace_repo.get_by_owner_id(user_id)
        name = name or fake.unique.file_name(category="image")
        path = os.path.join(config.features.photos_library_path, name)
        file = await file_factory(namespace.path, path, mediatype=mediatype)
        return MediaItem(
            file_id=file.id,
            name=file.name,
            size=file.size,
            mtime=file.mtime,
            mediatype=mediatype,
        )
    return factory


@pytest.fixture
def namespace_factory(namespace_repo: INamespaceRepository):
    """A factory to persist Namespace to the EdgeDB."""
    async def factory(path: AnyPath, owner_id: UUID):
        return await namespace_repo.save(
            Namespace(
                id=SENTINEL_ID,
                path=str(path),
                owner_id=uuid.UUID(str(owner_id)),
            )
        )
    return factory


@pytest.fixture
def mount_factory(mount_repo: IMountRepository) -> MountFactory:
    """A factory to mount file/folder into another folder."""
    async def factory(source_file_id: UUID, target_folder_id: UUID, display_name: str):
        query = """
            WITH
                source := (SELECT File FILTER .id = <uuid>$source_file_id),
                target_folder := (SELECT File FILTER .id = <uuid>$target_folder_id),
            SELECT (
                INSERT FileMemberMountPoint {
                    display_name := <str>$display_name,
                    parent := target_folder,
                    member := (
                        INSERT FileMember {
                            actions := 0,
                            created_at := std::datetime_current(),
                            user := target_folder.namespace.owner,
                            file := source,
                        }
                    )
                }
            ) {
                parent: { namespace: { path }, path },
                member: { actions },
            }
        """
        obj = await mount_repo.conn.query_required_single(  # type: ignore
            query,
            display_name=display_name,
            source_file_id=source_file_id,
            target_folder_id=target_folder_id,
        )
        display_path = Path(obj.parent.path) / display_name
        return await mount_repo.get_closest(obj.parent.namespace.path, display_path)
    return factory


@pytest.fixture
def shared_link_factory(shared_link_repo: ISharedLinkRepository) -> SharedLinkFactory:
    """A factory to persist SharedLink to the EdgeDB."""
    async def factory(file_id: UUID) -> SharedLink:
        return await shared_link_repo.save(
            SharedLink(
                id=SENTINEL_ID,
                file_id=file_id,
                token=uuid.uuid4().hex,
            )
        )
    return factory


@pytest.fixture
def user_factory(user_repo: IUserRepository):
    """A factory to persist User to the EdgeDB."""
    async def factory(username: str | None = None, password: str | None = None):
        return await user_repo.save(
            User(
                id=SENTINEL_ID,
                username=username or fake.unique.user_name(),
                password=password or fake.password(),
                superuser=False,
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
async def file(namespace: Namespace, file_factory: FileFactory):
    """A File instance saved to the EdgeDB."""
    return await file_factory(namespace.path)


@pytest.fixture
async def namespace_a(user_a: User, namespace_factory: NamespaceFactory):
    """A Namespace instance saved to the EdgeDB."""
    return await namespace_factory(user_a.username.lower(), owner_id=user_a.id)


@pytest.fixture
async def namespace_b(user_b: User, namespace_factory: NamespaceFactory):
    """A Namespace instance saved to the EdgeDB."""
    return await namespace_factory(user_b.username.lower(), owner_id=user_b.id)


@pytest.fixture
async def namespace(namespace_a: Namespace):
    """A Namespace instance saved to the EdgeDB."""
    return namespace_a


@pytest.fixture
async def shared_link(shared_link_factory: SharedLinkFactory, file: File):
    """A SharedLink instance saved to the EdgeDB."""
    return await shared_link_factory(file.id)


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
async def user_a(user_factory: UserFactory):
    """A User instance saved to the EdgeDB."""
    return await user_factory()


@pytest.fixture
async def user_b(user_factory: UserFactory):
    """A User instance saved to the EdgeDB."""
    return await user_factory()


@pytest.fixture
async def user(user_a: User):
    """A User instance saved to the EdgeDB."""
    return user_a


@pytest.fixture
async def bookmark(bookmark_repo: IBookmarkRepository, file: File, user: User):
    bookmark = Bookmark(user_id=user.id, file_id=file.id)
    return await bookmark_repo.save(bookmark)
