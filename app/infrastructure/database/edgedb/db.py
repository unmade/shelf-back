from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

import edgedb

from .repositories import (
    AccountRepository,
    FileRepository,
    FolderRepository,
    NamespaceRepository,
    UserRepository,
)

if TYPE_CHECKING:
    from .typedefs import EdgeDBContext

db_context: EdgeDBContext = ContextVar("db_context")


class EdgeDBDatabase:
    def __init__(
        self,
        dsn: str | None,
        max_concurrency: int | None,
        tls_ca_file: str = None,
        tls_security: str = None,
    ) -> None:
        self.client = edgedb.create_async_client(
            dsn=dsn,
            max_concurrency=max_concurrency,
            tls_ca_file=tls_ca_file,
            tls_security=tls_security,
        )
        db_context.set(self.client)

        self.account = AccountRepository(db_context=db_context)
        self.folder = FolderRepository(db_context=db_context)
        self.file = FileRepository(db_context=db_context)
        self.namespace = NamespaceRepository(db_context=db_context)
        self.user = UserRepository(db_context=db_context)
