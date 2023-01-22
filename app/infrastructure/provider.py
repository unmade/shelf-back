from __future__ import annotations

from typing import TYPE_CHECKING

from app.app.services import NamespaceService, UserService
from app.app.usecases import SignUp

if TYPE_CHECKING:
    from app.storage.base import Storage

    from .database.edgedb import EdgeDBDatabase

__all__ = ["Provider", "Service", "UseCase"]


class Provider:
    __slots__ = ["service", "usecase"]

    def __init__(self, database: EdgeDBDatabase, storage: Storage):
        self.service = Service(database=database, storage=storage)
        self.usecase = UseCase(self.service)


class Service:
    __slots__ = ["namespace", "user"]

    def __init__(self, database: EdgeDBDatabase, storage: Storage):
        self.namespace = NamespaceService(
            namespace_repo=database.namespace,
            folder_repo=database.folder,
            file_repo=database.file,
            fingerprint_repo=database.fingerprint,
            metadata_repo=database.metadata,
            storage=storage,
        )

        self.user = UserService(
            account_repo=database.account,
            user_repo=database.user,
        )


class UseCase:
    __slots__ = ["signup"]

    def __init__(self, services: Service):
        self.signup = SignUp(
            namespace_service=services.namespace,
            user_service=services.user,
        )
