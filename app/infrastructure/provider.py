from __future__ import annotations

from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from app.app.infrastructure.storage import IStorage

    from .database.edgedb import EdgeDBDatabase

__all__ = [
    "Provider",
    "Services",
    "UseCases",
]


class Provider:
    __slots__ = ["services", "usecases"]

    def __init__(self, database: EdgeDBDatabase, storage: IStorage):
        self.services = Services(database=database, storage=storage)
        self.usecases = UseCases(self.services)


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
