from __future__ import annotations

import uuid
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Protocol, Self

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


__all__ = [
    "SENTINEL_ID",
    "IDatabase",
    "ITransaction",
]


SENTINEL_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


class ITransaction(Protocol, AbstractAsyncContextManager["ITransaction"]):
    """An interface for a database transaction."""


class IAtomic(Protocol):
    def atomic(self, *, attempts: int = 3) -> AsyncIterator[ITransaction]:
        """
        Opens a retryable atomic block.

        All database operations either all occurs, or nothing occurs. The atomic block
        will attempt to re-execute its body if a transient error occurs, such as a
        network error or a transaction serialization error.

        Nested atomic blocks are allowed, but they will act as no-op.
        """


class IDatabase(IAtomic, Protocol):
    async def __aenter__(self) -> Self:
        return self  # pragma: no cover

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()

    async def migrate(self) -> None:
        """Migrates database to the latest schema."""

    async def shutdown(self) -> None:
        """Performs all necessary actions to shutdown database correctly."""
