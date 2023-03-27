from __future__ import annotations

from typing import TYPE_CHECKING

from app.app.files.services import (
    DuplicateFinderService,
    FileCoreService,
    MetadataService,
    NamespaceService,
    SharingService,
)
from app.app.files.usecases import NamespaceUseCase, SharingUseCase
from app.app.users.services import UserService

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
    __slots__ = ["dupefinder", "filecore", "metadata", "namespace", "sharing", "user"]

    def __init__(self, database: EdgeDBDatabase, storage: IStorage):
        self.filecore = FileCoreService(database=database, storage=storage)
        self.dupefinder = DuplicateFinderService(database=database)
        self.metadata = MetadataService(database=database)
        self.namespace = NamespaceService(database=database)
        self.sharing = SharingService(database=database)
        self.user = UserService(database=database)


class UseCases:
    __slots__ = ["namespace", "sharing"]

    def __init__(self, services: Services):
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
