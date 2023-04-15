from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator, Self

import edgedb
from edgedb.asyncio_client import AsyncIOIteration

from app.app.audit.repositories import IAuditTrailRepository
from app.app.files.repositories import (
    IContentMetadataRepository,
    IFileRepository,
    IFingerprintRepository,
    INamespaceRepository,
    ISharedLinkRepository,
)
from app.app.infrastructure import IDatabase
from app.app.users.repositories import (
    IAccountRepository,
    IBookmarkRepository,
    IUserRepository,
)
from app.config import EdgeDBConfig

from .repositories import (
    AccountRepository,
    AuditTrailRepository,
    BookmarkRepository,
    ContentMetadataRepository,
    FileRepository,
    FingerprintRepository,
    NamespaceRepository,
    SharedLinkRepository,
    UserRepository,
)

if TYPE_CHECKING:
    from .typedefs import EdgeDBContext

db_context: EdgeDBContext = ContextVar("db_context")


class EdgeDBDatabase(IDatabase):
    account: IAccountRepository
    audit_trail: IAuditTrailRepository
    bookmark: IBookmarkRepository
    file: IFileRepository
    fingerprint: IFingerprintRepository
    metadata: IContentMetadataRepository
    namespace: INamespaceRepository
    shared_link: ISharedLinkRepository
    user: IUserRepository

    def __init__(self, config: EdgeDBConfig) -> None:
        self.config = config
        self.client = edgedb.create_async_client(
            dsn=config.dsn,
            max_concurrency=config.edgedb_max_concurrency,
            tls_ca_file=config.edgedb_tls_ca_file,
            tls_security=config.edgedb_tls_security,
        )
        db_context.set(self.client)

        self.account= AccountRepository(db_context=db_context)
        self.audit_trail = AuditTrailRepository(db_context=db_context)
        self.bookmark = BookmarkRepository(db_context=db_context)
        self.file = FileRepository(db_context=db_context)
        self.fingerprint = FingerprintRepository(db_context=db_context)
        self.metadata = ContentMetadataRepository(db_context=db_context)
        self.namespace = NamespaceRepository(db_context=db_context)
        self.shared_link = SharedLinkRepository(db_context=db_context)
        self.user = UserRepository(db_context=db_context)

    async def __aenter__(self) -> Self:
        await self.client.__aenter__()
        return self

    async def atomic(self, attempts: int = 3) -> AsyncIterator[None]:
        if isinstance(db_context.get(), AsyncIOIteration):
            yield
            return

        tx_client = self.client.with_retry_options(edgedb.RetryOptions(attempts))
        async for tx in tx_client.transaction():
            async with tx:
                token = db_context.set(tx)
                try:
                    yield
                finally:
                    db_context.reset(token)

    async def migrate(self) -> None:
        schema = Path(self.config.edgedb_schema).read_text()
        async for tx in self.client.transaction():
            async with tx:
                await tx.execute(f"""
                    START MIGRATION TO {{
                        {schema}
                    }};
                    POPULATE MIGRATION;
                    COMMIT MIGRATION;
                """)

    async def shutdown(self) -> None:
        await self.client.aclose()
