from __future__ import annotations

from typing import TYPE_CHECKING

from app.app.services import (
    DuplicateFinderService,
    FileCoreService,
    MetadataService,
    NamespaceService,
    UserService,
)
from app.app.usecases import SignUp, UploadFile

if TYPE_CHECKING:
    from app.app.infrastructure.storage import IStorage

    from .database.edgedb import EdgeDBDatabase

__all__ = ["Provider", "Service", "UseCase"]


class Provider:
    __slots__ = ["service", "usecase"]

    def __init__(self, database: EdgeDBDatabase, storage: IStorage):
        self.service = Service(database=database, storage=storage)
        self.usecase = UseCase(self.service)


class Service:
    __slots__ = ["namespace", "user"]

    def __init__(self, database: EdgeDBDatabase, storage: IStorage):
        filecore = FileCoreService(database=database, storage=storage)
        dupefinder = DuplicateFinderService(database=database)
        metadata = MetadataService(database=database)
        self.namespace = NamespaceService(
            database=database,
            filecore=filecore,
            dupefinder=dupefinder,
            metadata=metadata,
        )
        self.user = UserService(database=database)


class UseCase:
    __slots__ = ["signup", "upload_file"]

    def __init__(self, services: Service):
        self.signup = SignUp(
            namespace_service=services.namespace,
            user_service=services.user,
        )
        self.upload_file = UploadFile(
            namespace_service=services.namespace,
            user_service=services.user,
        )
