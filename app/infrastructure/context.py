from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Self, assert_never

from app.app.audit.services import AuditTrailService
from app.app.auth.services import TokenService
from app.app.auth.usecases import AuthUseCase
from app.app.files.services import (
    DuplicateFinderService,
    FileService,
    MetadataService,
    NamespaceService,
    SharingService,
    ThumbnailService,
)
from app.app.files.services.content import ContentService
from app.app.files.services.file import FileCoreService, MountService
from app.app.files.services.file_member import FileMemberService
from app.app.files.usecases import NamespaceUseCase, SharingUseCase
from app.app.photos.services import MediaItemService
from app.app.photos.usecases import PhotosUseCase
from app.app.users.services import BookmarkService, UserService
from app.app.users.usecases import UserUseCase
from app.cache import cache
from app.config import FileSystemStorageConfig, S3StorageConfig
from app.infrastructure.clients.indexer import IndexerClient
from app.infrastructure.database.edgedb import EdgeDBDatabase
from app.infrastructure.storage import FileSystemStorage, S3Storage
from app.infrastructure.worker import ARQWorker
from app.toolkit import taskgroups

if TYPE_CHECKING:
    from app.app.infrastructure import IIndexerClient, IStorage, IWorker
    from app.app.infrastructure.database import ITransaction
    from app.config import (
        AppConfig,
        DatabaseConfig,
        IndexerClientConfig,
        StorageConfig,
        WorkerConfig,
    )

__all__ = [
    "AppContext",
    "UseCases",
]


class AppContext:
    __slots__ = ["usecases", "_infra", "_stack"]

    def __init__(self, config: AppConfig):
        self._stack = AsyncExitStack()
        self._infra = Infrastructure(config)
        services = Services(self._infra)
        self.usecases = UseCases(services)

    async def __aenter__(self) -> Self:
        await self._stack.enter_async_context(self._infra)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await taskgroups.wait_background_tasks(timeout=30)
        await self._stack.aclose()


class Infrastructure:
    __slots__ = ["database", "indexer", "storage", "worker", "_stack"]

    def __init__(self, config: AppConfig):
        self.database = self._get_database(config.database)
        self.storage = self._get_storage(config.storage)
        self.indexer = self._get_indexer(config.indexer)
        self.worker = self._get_worker(config.worker)
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> Self:
        ctx = [
            self._stack.enter_async_context(self.database),
            self._stack.enter_async_context(self.storage),
            self._stack.enter_async_context(self.worker),
        ]
        if self.indexer is not None:
            ctx.append(self._stack.enter_async_context(self.indexer))

        await taskgroups.gather(*ctx)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._stack.aclose()

    @staticmethod
    def _get_database(db_config: DatabaseConfig) -> EdgeDBDatabase:
        return EdgeDBDatabase(db_config)

    @staticmethod
    def _get_indexer(indexer_config: IndexerClientConfig) -> IIndexerClient | None:
        if indexer_config.url is None:
            return None
        return IndexerClient(indexer_config)

    @staticmethod
    def _get_storage(storage_config: StorageConfig) -> IStorage:
        if isinstance(storage_config, S3StorageConfig):
            return S3Storage(storage_config)
        if isinstance(storage_config, FileSystemStorageConfig):
            return FileSystemStorage(storage_config)
        assert_never(storage_config)

    @staticmethod
    def _get_worker(worker_config: WorkerConfig) -> IWorker:
        return ARQWorker(worker_config)


class Services:
    __slots__ = [
        "_database",
        "audit_trail",
        "bookmark",
        "content",
        "dupefinder",
        "file",
        "filecore",
        "file_member",
        "media_item",
        "metadata",
        "namespace",
        "sharing",
        "thumbnailer",
        "token",
        "user",
    ]

    def __init__(self, infra: Infrastructure):
        database = infra.database
        storage = infra.storage
        worker = infra.worker

        self._database = database

        self.audit_trail = AuditTrailService(database=database)
        self.bookmark = BookmarkService(database=database)
        self.filecore = FileCoreService(
            database=database,
            storage=storage,
            worker=worker,
        )
        self.file = FileService(
            filecore=self.filecore,
            mount_service=MountService(database=database),
        )
        self.file_member = FileMemberService(database=database)
        self.dupefinder = DuplicateFinderService(database=database)
        self.media_item = MediaItemService(database=database)
        self.metadata = MetadataService(database=database)
        self.namespace = NamespaceService(database=database, filecore=self.filecore)
        self.sharing = SharingService(database=database)
        self.thumbnailer = ThumbnailService(filecore=self.filecore, storage=storage)
        self.token = TokenService(token_repo=cache)
        self.user = UserService(database=database)

        self.content = ContentService(
            dupefinder=self.dupefinder,
            filecore=self.filecore,
            indexer=infra.indexer,
            metadata=self.metadata,
            thumbnailer=self.thumbnailer,
            worker=worker,
        )

    def atomic(self, *, attempts: int = 3) -> AsyncIterator[ITransaction]:
        return self._database.atomic(attempts=attempts)


class UseCases:
    __slots__ = ["auth", "namespace", "photos", "sharing", "user"]

    def __init__(self, services: Services):
        self.auth = AuthUseCase(services=services)
        self.namespace = NamespaceUseCase(services=services)
        self.sharing = SharingUseCase(services=services)
        self.photos = PhotosUseCase(services=services)
        self.user = UserUseCase(services=services)
