from __future__ import annotations

from contextlib import AsyncExitStack
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator, Self

import edgedb
from edgedb.asyncio_client import AsyncIOIteration

from app.app.infrastructure import IDatabase
from app.app.photos.repositories import IAlbumRepository
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
    FileMemberRepository,
    FilePendingDeletionRepository,
    FileRepository,
    FingerprintRepository,
    MediaItemRepository,
    MountRepository,
    NamespaceRepository,
    SharedLinkRepository,
    UserRepository,
)

if TYPE_CHECKING:
    from app.app.audit.repositories import IAuditTrailRepository
    from app.app.files.repositories import (
        IContentMetadataRepository,
        IFileMemberRepository,
        IFilePendingDeletionRepository,
        IFileRepository,
        IFingerprintRepository,
        IMountRepository,
        INamespaceRepository,
        ISharedLinkRepository,
    )
    from app.app.infrastructure.database import ITransaction
    from app.app.photos.repositories import IMediaItemRepository

    from .typedefs import EdgeDBContext

db_context: EdgeDBContext = ContextVar("db_context")


class Transaction(AsyncExitStack):
    def __init__(self, tx: AsyncIOIteration) -> None:
        super().__init__()
        self._tx = tx

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        if not self._tx._managed:
            await self.enter_async_context(self._tx)
            token = db_context.set(self._tx)
            self.callback(db_context.reset, token)
        return self


class EdgeDBDatabase(IDatabase):
    album: IAlbumRepository
    account: IAccountRepository
    audit_trail: IAuditTrailRepository
    bookmark: IBookmarkRepository
    file: IFileRepository
    file_member: IFileMemberRepository
    file_pending_deletion: IFilePendingDeletionRepository
    fingerprint: IFingerprintRepository
    media_item: IMediaItemRepository
    metadata: IContentMetadataRepository
    mount: IMountRepository
    namespace: INamespaceRepository
    shared_link: ISharedLinkRepository
    user: IUserRepository

    def __init__(self, config: EdgeDBConfig) -> None:
        self._stack = AsyncExitStack()

        self.config = config
        self.client = edgedb.create_async_client(
            dsn=str(config.dsn),
            max_concurrency=config.edgedb_max_concurrency,
            tls_ca_file=config.edgedb_tls_ca_file,
            tls_security=config.edgedb_tls_security,
        )
        db_context.set(self.client)

        self.account= AccountRepository(db_context=db_context)
        self.audit_trail = AuditTrailRepository(db_context=db_context)
        self.bookmark = BookmarkRepository(db_context=db_context)
        self.file = FileRepository(db_context=db_context)
        self.file_member = FileMemberRepository(db_context=db_context)
        self.file_pending_deletion = FilePendingDeletionRepository(
            db_context=db_context
        )
        self.fingerprint = FingerprintRepository(db_context=db_context)
        self.media_item = MediaItemRepository(db_context=db_context)
        self.metadata = ContentMetadataRepository(db_context=db_context)
        self.mount = MountRepository(db_context=db_context)
        self.namespace = NamespaceRepository(db_context=db_context)
        self.shared_link = SharedLinkRepository(db_context=db_context)
        self.user = UserRepository(db_context=db_context)

    async def __aenter__(self) -> Self:
        await self._stack.enter_async_context(self.client)
        return self

    async def atomic(self, attempts: int = 3) -> AsyncIterator[ITransaction]:
        value = db_context.get()
        if isinstance(value, AsyncIOIteration):
            yield Transaction(value)
            return

        tx_client = self.client.with_retry_options(edgedb.RetryOptions(attempts))
        async for tx in tx_client.transaction():
            yield Transaction(tx)

    async def migrate(self) -> None:  # pragma: no cover
        schema = Path(self.config.edgedb_schema).read_text()
        async for tx in self.client.transaction():
            async with tx:
                await tx.execute(
                    f"""
                        START MIGRATION TO {{
                            {schema}
                        }};
                        POPULATE MIGRATION;
                        COMMIT MIGRATION;
                    """
                )

    async def shutdown(self) -> None:
        await self._stack.aclose()
