from __future__ import annotations

from typing import TYPE_CHECKING

from app.app.files.services import (
    DuplicateFinderService,
    FileCoreService,
    MetadataService,
    NamespaceService,
    SharingService,
)
from app.app.managers import NamespaceManager, SharingManager
from app.app.usecases import SignUp
from app.app.users.services import UserService

if TYPE_CHECKING:
    from app.app.infrastructure.storage import IStorage

    from .database.edgedb import EdgeDBDatabase

__all__ = [
    "Manager",
    "Provider",
    "Service",
    "UseCase",
]


class Provider:
    __slots__ = ["service", "usecase", "manager"]

    def __init__(self, database: EdgeDBDatabase, storage: IStorage):
        self.service = Service(database=database, storage=storage)
        self.manager = Manager(self.service)
        self.usecase = UseCase(self.manager, self.service)


class Service:
    __slots__ = ["dupefinder", "filecore", "metadata", "namespace", "sharing", "user"]

    def __init__(self, database: EdgeDBDatabase, storage: IStorage):
        self.filecore = FileCoreService(database=database, storage=storage)
        self.dupefinder = DuplicateFinderService(database=database)
        self.metadata = MetadataService(database=database)
        self.namespace = NamespaceService(database=database)
        self.sharing = SharingService(database=database)
        self.user = UserService(database=database)


class Manager:
    __slots__ = ["namespace", "sharing"]

    def __init__(self, services: Service):
        self.namespace = NamespaceManager(
            dupefinder=services.dupefinder,
            filecore=services.filecore,
            metadata=services.metadata,
            namespace=services.namespace,
            user=services.user,
        )
        self.sharing = SharingManager(
            filecore=services.filecore,
            sharing=services.sharing,
        )


class UseCase:
    __slots__ = ["signup"]

    def __init__(self, manager: Manager, services: Service):
        self.signup = SignUp(
            ns_manager=manager.namespace,
            user_service=services.user,
        )
