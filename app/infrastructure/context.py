from __future__ import annotations

from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Self, assert_never

from app.app.auth.services import TokenService
from app.app.auth.usecases import AuthUseCase
from app.app.files.services import (
    DuplicateFinderService,
    FileCoreService,
    MetadataService,
    NamespaceService,
    SharingService,
)
from app.app.files.usecases import NamespaceUseCase, SharingUseCase
from app.app.users.services import BookmarkService, UserService
from app.app.users.usecases import UserUseCase
from app.cache import cache
from app.config import (
    DatabaseConfig,
    FileSystemStorageConfig,
    S3StorageConfig,
    StorageConfig,
)
from app.infrastructure.database.edgedb import EdgeDBDatabase
from app.infrastructure.storage import FileSystemStorage, S3Storage

if TYPE_CHECKING:
    from app.app.infrastructure.storage import IStorage


__all__ = [
    "AppContext",
    "UseCases",
]


class AppContext:
    __slots__ = ["usecases", "_stack", "_infra"]

    def __init__(self, db_config: DatabaseConfig, storage_config: StorageConfig):
        self._stack = AsyncExitStack()
        self._infra = Infrastructure(db_config, storage_config)
        services = Services(self._infra.database, self._infra.storage)
        self.usecases = UseCases(services)

    async def __aenter__(self) -> Self:
        await self._stack.enter_async_context(self._infra)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._stack.aclose()


class Infrastructure:
    __slots__ = ["database", "storage", "_stack"]

    def __init__(self, db_config: DatabaseConfig, storage_config: StorageConfig):
        self.database = self._get_database(db_config)
        self.storage = self._get_storage(storage_config)
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> Self:
        await self._stack.enter_async_context(self.database)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._stack.aclose()

    @staticmethod
    def _get_database(db_config: DatabaseConfig) -> EdgeDBDatabase:
        return EdgeDBDatabase(db_config)

    @staticmethod
    def _get_storage(storage_config: StorageConfig) -> IStorage:
        if isinstance(storage_config, S3StorageConfig):
            return S3Storage(storage_config)
        if isinstance(storage_config, FileSystemStorageConfig):
            return FileSystemStorage(storage_config)
        assert_never(storage_config)


class Services:
    __slots__ = [
        "bookmark",
        "dupefinder",
        "filecore",
        "metadata",
        "namespace",
        "sharing",
        "token",
        "user",
    ]

    def __init__(self, database: EdgeDBDatabase, storage: IStorage):
        self.bookmark = BookmarkService(database=database)
        self.filecore = FileCoreService(database=database, storage=storage)
        self.dupefinder = DuplicateFinderService(database=database)
        self.metadata = MetadataService(database=database)
        self.namespace = NamespaceService(database=database, filecore=self.filecore)
        self.sharing = SharingService(database=database)
        self.token = TokenService(token_repo=cache)
        self.user = UserService(database=database)


class UseCases:
    __slots__ = ["auth", "namespace", "sharing", "user"]

    def __init__(self, services: Services):
        self.auth = AuthUseCase(
            namespace_service=services.namespace,
            token_service=services.token,
            user_service=services.user,
        )
        self.namespace = NamespaceUseCase(
            dupefinder=services.dupefinder,
            filecore=services.filecore,
            metadata=services.metadata,
            namespace=services.namespace,
            user=services.user,
        )
        self.sharing = SharingUseCase(
            filecore=services.filecore,
            sharing=services.sharing,
        )
        self.user = UserUseCase(
            bookmark_service=services.bookmark,
            filecore=services.filecore,
            namespace_service=services.namespace,
            user_service=services.user,
        )
