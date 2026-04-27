from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from faker import Faker

from app.app.blobs.domain import Blob, BlobMetadata
from app.app.files.domain import (
    ContentMetadata,
    File,
    FileMember,
    FilePendingDeletion,
    Fingerprint,
    MountPoint,
    Namespace,
    Path,
    SharedLink,
)
from app.app.infrastructure.database import SENTINEL_ID
from app.app.photos.domain import Album, MediaItem
from app.app.users.domain import Account, User
from app.infrastructure.database.tortoise import models
from app.toolkit import chash, timezone
from app.toolkit.mediatypes import MediaType
from app.toolkit.metadata import Exif

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Protocol
    from uuid import UUID

    from app.app.audit.repositories import IAuditTrailRepository
    from app.app.blobs.repositories import IBlobMetadataRepository, IBlobRepository
    from app.app.files.domain import AnyPath
    from app.app.files.repositories import (
        IContentMetadataRepository,
        IFileMemberRepository,
        IFilePendingDeletionRepository,
        IFileRepository,
        IFingerprintRepository,
        IMountRepository,
        INamespaceRepository,
        ISharedLinkRepository,
    )
    from app.app.photos.repositories import (
        IAlbumRepository,
        IMediaItemFavouriteRepository,
        IMediaItemRepository,
    )
    from app.app.users.repositories import (
        IAccountRepository,
        IBookmarkRepository,
        IUserRepository,
    )
    from app.infrastructure.database.tortoise import TortoiseDatabase

    class AlbumFactory(Protocol):
        async def __call__(
            self,
            owner_id: UUID,
            title: str | None = None,
            *,
            cover_media_item_id: UUID | None = None,
            items: Iterable[MediaItem] | None = None,
        ) -> Album: ...

    class BlobFactory(Protocol):
        async def __call__(
            self,
            storage_key: str | None = None,
            size: int = 10,
            chash: str | None = None,
            media_type: str = "plain/text",
        ) -> Blob:
            ...

    class BlobMetadataFactory(Protocol):
        async def __call__(self, blob_id: UUID, data: Exif) -> BlobMetadata: ...

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

    class FilePendingDeletionFactory(Protocol):
        async def __call__(
            self,
            storage_key: str | None = None,
            mediatype: str | None = None,
        ) -> FilePendingDeletion: ...

    class FingerprintFactory(Protocol):
        async def __call__(self, file_id: UUID, value: int) -> Fingerprint: ...

    class FolderFactory(Protocol):
        async def __call__(
            self,
            ns_path: str,
            path: AnyPath | None = None,
            size: int = 0,
        ) -> File:
            ...

    class NamespaceFactory(Protocol):
        async def __call__(self, path: str, owner_id: UUID) -> Namespace:
            ...

    class MountFactory(Protocol):
        async def __call__(
            self,
            source_file_id: UUID,
            target_folder_id: UUID,
            display_name: str,
        ) -> MountPoint:
            ...

    class MediaItemFactory(Protocol):
        async def __call__(
            self,
            owner_id: UUID,
            name: str | None = None,
            media_type: str = ...,
            modified_at: datetime | None = None,
            deleted_at: datetime | None = None,
        ) -> MediaItem: ...

    class SharedLinkFactory(Protocol):
        async def __call__(self, file_id: UUID) -> SharedLink: ...

    class UserFactory(Protocol):
        async def __call__(
            self,
            username: str | None = None,
            password: str | None = None,
            email: str | None = None,
        ) -> User:
            ...


fake = Faker()


@pytest.fixture
def account_repo(tortoise_database: TortoiseDatabase) -> IAccountRepository:
    return tortoise_database.account


@pytest.fixture
def album_repo(tortoise_database: TortoiseDatabase) -> IAlbumRepository:
    return tortoise_database.album


@pytest.fixture
def audit_trail_repo(tortoise_database: TortoiseDatabase) -> IAuditTrailRepository:
    return tortoise_database.audit_trail


@pytest.fixture
def blob_repo(tortoise_database: TortoiseDatabase) -> IBlobRepository:
    return tortoise_database.blob


@pytest.fixture
def blob_metadata_repo(
    tortoise_database: TortoiseDatabase,
) -> IBlobMetadataRepository:
    return tortoise_database.blob_metadata


@pytest.fixture
def bookmark_repo(tortoise_database: TortoiseDatabase) -> IBookmarkRepository:
    return tortoise_database.bookmark


@pytest.fixture
def fingerprint_repo(tortoise_database: TortoiseDatabase) -> IFingerprintRepository:
    return tortoise_database.fingerprint


@pytest.fixture
def file_member_repo(tortoise_database: TortoiseDatabase) -> IFileMemberRepository:
    return tortoise_database.file_member


@pytest.fixture
def file_pending_deletion_repo(
    tortoise_database: TortoiseDatabase,
) -> IFilePendingDeletionRepository:
    return tortoise_database.file_pending_deletion


@pytest.fixture
def file_repo(tortoise_database: TortoiseDatabase) -> IFileRepository:
    return tortoise_database.file


@pytest.fixture
def media_item_repo(tortoise_database: TortoiseDatabase) -> IMediaItemRepository:
    return tortoise_database.media_item


@pytest.fixture
def media_item_favourite_repo(
    tortoise_database: TortoiseDatabase,
) -> IMediaItemFavouriteRepository:
    return tortoise_database.media_item_favourite


@pytest.fixture
def metadata_repo(tortoise_database: TortoiseDatabase) -> IContentMetadataRepository:
    return tortoise_database.metadata


@pytest.fixture
def mount_repo(tortoise_database: TortoiseDatabase) -> IMountRepository:
    return tortoise_database.mount


@pytest.fixture
def namespace_repo(tortoise_database: TortoiseDatabase) -> INamespaceRepository:
    return tortoise_database.namespace


@pytest.fixture
def shared_link_repo(
    tortoise_database: TortoiseDatabase,
) -> ISharedLinkRepository:
    return tortoise_database.shared_link


@pytest.fixture
def user_repo(tortoise_database: TortoiseDatabase) -> IUserRepository:
    return tortoise_database.user


@pytest.fixture
def user_factory(user_repo: IUserRepository) -> UserFactory:
    async def factory(
        username: str | None = None,
        password: str | None = None,
        email: str | None = None,
    ) -> User:
        return await user_repo.save(
            User(
                id=SENTINEL_ID,
                username=username or fake.unique.user_name(),
                password=password or fake.password(),
                email=email,
                email_verified=False,
                display_name="",
                active=True,
                superuser=False,
            )
        )
    return factory


@pytest.fixture
def album_factory(album_repo: IAlbumRepository) -> AlbumFactory:
    async def factory(
        owner_id: UUID,
        title: str | None = None,
        *,
        cover_media_item_id: UUID | None = None,
        items: Iterable[MediaItem] | None = None,
    ) -> Album:
        title = title or fake.unique.name()
        album = await album_repo.save(
            Album(
                id=SENTINEL_ID,
                title=title,
                owner_id=owner_id,
            )
        )

        if items:
            media_item_ids = [item.id for item in items]
            album = await album_repo.add_items(
                owner_id, album.slug, media_item_ids=media_item_ids
            )

        if cover_media_item_id:
            album = await album_repo.set_cover(
                owner_id, album.slug, cover_media_item_id
            )

        return album
    return factory


@pytest.fixture
def blob_factory(blob_repo: IBlobRepository) -> BlobFactory:
    async def factory(
        storage_key: str | None = None,
        size: int = 10,
        chash: str | None = None,
        media_type: str = "plain/text",
    ) -> Blob:
        return await blob_repo.save(
            Blob(
                id=SENTINEL_ID,
                storage_key=storage_key or f"blobs/{uuid.uuid7().hex}",
                size=size,
                chash=chash or uuid.uuid4().hex,
                media_type=media_type,
                created_at=timezone.now(),
            )
        )
    return factory


@pytest.fixture
def blob_metadata_factory(
    blob_metadata_repo: IBlobMetadataRepository,
) -> BlobMetadataFactory:
    async def factory(blob_id: UUID, data: Exif) -> BlobMetadata:
        return await blob_metadata_repo.save(BlobMetadata(blob_id=blob_id, data=data))
    return factory


@pytest.fixture
def file_factory(file_repo: IFileRepository) -> FileFactory:
    async def factory(
        ns_path: str,
        path: AnyPath | None = None,
        mediatype: str = "plain/text",
    ) -> File:
        if path is None:
            path = fake.unique.file_name(category="text", extension="txt")
        return await file_repo.save(
            File(
                id=SENTINEL_ID,
                ns_path=ns_path,
                name=Path(path).name,
                path=Path(path),
                chash=hashlib.sha256(str(path).encode()).hexdigest(),
                size=10,
                mediatype=mediatype,
            )
        )
    return factory


@pytest.fixture
def file_member_factory(
    file_member_repo: IFileMemberRepository,
) -> FileMemberFactory:
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
def folder_factory(file_repo: IFileRepository) -> FolderFactory:
    async def factory(
        ns_path: str, path: AnyPath | None = None, size: int = 0
    ) -> File:
        path = path or fake.unique.word()
        return await file_repo.save(
            File(
                id=SENTINEL_ID,
                ns_path=ns_path,
                name=Path(path).name,
                path=Path(path),
                chash=chash.EMPTY_CONTENT_HASH,
                size=size,
                mediatype=MediaType.FOLDER,
            )
        )
    return factory



@pytest.fixture
def fingerprint_factory(
    fingerprint_repo: IFingerprintRepository,
) -> FingerprintFactory:
    async def factory(file_id: UUID, value: int) -> Fingerprint:
        return await fingerprint_repo.save(Fingerprint(file_id, value=value))
    return factory


@pytest.fixture
def media_item_factory(
    media_item_repo: IMediaItemRepository,
    blob_factory: BlobFactory,
) -> MediaItemFactory:
    async def factory(
        owner_id: UUID,
        name: str | None = None,
        media_type: str = MediaType.IMAGE_JPEG,
        modified_at: datetime | None = None,
        deleted_at: datetime | None = None,
    ) -> MediaItem:
        now = timezone.now()
        name = name or fake.unique.file_name(category="image")
        blob = await blob_factory(
            storage_key=f"{owner_id}/photos/{now:%Y/%m/%d}/{name}",
            media_type=media_type,
        )
        deleted_at = deleted_at or None
        item = MediaItem(
            id=SENTINEL_ID,
            owner_id=owner_id,
            blob_id=blob.id,
            name=name,
            media_type=blob.media_type,
            size=blob.size,
            chash=blob.chash,
            taken_at=None,
            created_at=now,
            modified_at=modified_at or now,
            deleted_at=deleted_at,
        )
        return await media_item_repo.save(item)
    return factory


@pytest.fixture
def mount_factory(mount_repo: IMountRepository) -> MountFactory:
    async def factory(
        source_file_id: UUID,
        target_folder_id: UUID,
        display_name: str,
    ) -> MountPoint:
        target_folder = await models.File.get(id=target_folder_id)
        namespace = await models.Namespace.get(
            id=target_folder.namespace_id  # type: ignore[attr-defined]
        )
        owner_id = namespace.owner_id  # type: ignore[attr-defined]
        member = await models.FileMember.create(
            actions=0,
            created_at=datetime.now(UTC),
            user_id=owner_id,
            file_id=source_file_id,
        )
        await models.FileMemberMountPoint.create(
            display_name=display_name,
            member=member,
            parent_id=target_folder_id,
        )
        display_path = Path(target_folder.path) / display_name
        return await mount_repo.get_closest(namespace.path, display_path)
    return factory


@pytest.fixture
def namespace_factory():
    async def factory(path: str, owner_id: UUID) -> Namespace:
        obj = await models.Namespace.create(
            path=path,
            owner_id=owner_id,
        )
        return Namespace(id=obj.id, path=obj.path, owner_id=owner_id)
    return factory


@pytest.fixture
def file_pending_deletion_factory(
    file_pending_deletion_repo: IFilePendingDeletionRepository,
) -> FilePendingDeletionFactory:
    async def factory(
        storage_key: str | None = None,
        mediatype: str | None = None,
    ) -> FilePendingDeletion:
        items = await file_pending_deletion_repo.save_batch([
            FilePendingDeletion(
                id=SENTINEL_ID,
                storage_key=(
                    storage_key
                    or f"{fake.unique.user_name()}/{fake.unique.file_name()}"
                ),
                chash=uuid.uuid4().hex,
                mediatype=mediatype or "plain/text",
            )
        ])
        return items[0]
    return factory


@pytest.fixture
def shared_link_factory(
    shared_link_repo: ISharedLinkRepository,
) -> SharedLinkFactory:
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
async def account(user: User, account_repo: IAccountRepository) -> Account:
    return await account_repo.save(Account(id=SENTINEL_ID, user_id=user.id))


@pytest.fixture
async def namespace_a(user_a: User, namespace_factory: NamespaceFactory) -> Namespace:
    return await namespace_factory(user_a.username.lower(), owner_id=user_a.id)


@pytest.fixture
async def namespace_b(user_b: User, namespace_factory: NamespaceFactory) -> Namespace:
    return await namespace_factory(user_b.username.lower(), owner_id=user_b.id)


@pytest.fixture
async def namespace(namespace_a: Namespace) -> Namespace:
    return namespace_a


@pytest.fixture
async def user_a(user_factory: UserFactory) -> User:
    return await user_factory()


@pytest.fixture
async def user_b(user_factory: UserFactory) -> User:
    return await user_factory()


@pytest.fixture
async def user(user_a: User) -> User:
    return user_a


@pytest.fixture
async def file(
    file_factory: FileFactory, namespace: Namespace
) -> File:
    return await file_factory(namespace.path)


@pytest.fixture
async def content_metadata(
    metadata_repo: IContentMetadataRepository, file: File
) -> ContentMetadata:
    exif = Exif(width=1280, height=800)
    return await metadata_repo.save(
        ContentMetadata(file_id=file.id, data=exif)
    )


@pytest.fixture
async def shared_link(
    shared_link_factory: SharedLinkFactory, file: File
) -> SharedLink:
    return await shared_link_factory(file.id)
