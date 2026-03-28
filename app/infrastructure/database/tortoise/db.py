from __future__ import annotations

from typing import TYPE_CHECKING, Self

from tortoise import Tortoise, TortoiseConfig, connections, transactions
from tortoise.config import AppConfig, DBUrlConfig

from app.app.infrastructure import IDatabase

from .repositories import (
    AccountRepository,
    AlbumRepository,
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
    from collections.abc import AsyncIterator

    from app.app.infrastructure.database import ITransaction
    from app.config import PostgresConfig, SQLiteConfig


TORTOISE_MODELS = ["app.infrastructure.database.tortoise.models"]


class Transaction:
    __slots__ = ("_connection_name", "_tx_ctx")

    def __init__(self, connection_name: str | None = None) -> None:
        self._connection_name = connection_name
        self._tx_ctx = transactions.in_transaction(self._connection_name)

    async def __aenter__(self) -> Self:
        await self._tx_ctx.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._tx_ctx.__aexit__(exc_type, exc_val, exc_tb)


class TortoiseDatabase(IDatabase):
    def __init__(self, config: SQLiteConfig | PostgresConfig) -> None:
        self.config = config
        self.account = AccountRepository()
        self.album = AlbumRepository()
        self.audit_trail = AuditTrailRepository()
        self.bookmark = BookmarkRepository()
        self.file = FileRepository()
        self.file_member = FileMemberRepository()
        self.file_pending_deletion = FilePendingDeletionRepository()
        self.fingerprint = FingerprintRepository()
        self.media_item = MediaItemRepository()
        self.metadata = ContentMetadataRepository()
        self.mount = MountRepository()
        self.namespace = NamespaceRepository()
        self.shared_link = SharedLinkRepository()
        self.user = UserRepository()

    def _tortoise_config(self) -> TortoiseConfig:
        return TortoiseConfig(
            connections={
                "default": DBUrlConfig(self.config.db_url),
            },
            apps={
                "models": AppConfig(
                    models=TORTOISE_MODELS,
                ),
            },
        )

    async def __aenter__(self) -> Self:
        await Tortoise.init(config=self._tortoise_config())
        return self

    async def atomic(self, attempts: int = 3) -> AsyncIterator[ITransaction]:
        yield Transaction()

    async def migrate(self) -> None:
        await Tortoise.generate_schemas()

    async def shutdown(self) -> None:
        await connections.close_all()
