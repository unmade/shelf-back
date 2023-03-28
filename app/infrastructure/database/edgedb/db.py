from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, AsyncIterator, Self

import edgedb
from edgedb.asyncio_client import AsyncIOIteration

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

from .repositories import (
    AccountRepository,
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
    bookmark: IBookmarkRepository
    file: IFileRepository
    fingerprint: IFingerprintRepository
    metadata: IContentMetadataRepository
    namespace: INamespaceRepository
    shared_link: ISharedLinkRepository
    user: IUserRepository

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

        self.account= AccountRepository(db_context=db_context)
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

    async def shutdown(self) -> None:
        await self.client.aclose()
