from __future__ import annotations

from typing import TYPE_CHECKING, Self

from tortoise import Tortoise, TortoiseConfig, connections, transactions
from tortoise.config import AppConfig, DBUrlConfig

from app.app.infrastructure import IDatabase

from .repositories import AccountRepository, BookmarkRepository, UserRepository

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.app.infrastructure.database import ITransaction
    from app.config import PostgresConfig, SQLiteConfig


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
        self.bookmark = BookmarkRepository()
        self.user = UserRepository()

    def _tortoise_config(self) -> TortoiseConfig:
        return TortoiseConfig(
            connections={
                "default": DBUrlConfig(self.config.db_url),
            },
            apps={
                "models": AppConfig(
                    models=["app.infrastructure.database.tortoise.models"],
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
