from __future__ import annotations

import uuid
from contextlib import AbstractAsyncContextManager
from typing import Protocol, Self

__all__ = [
    "SENTINEL_ID",
    "IDatabase",
    "ITransaction",
]


SENTINEL_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


class ITransaction(Protocol, AbstractAsyncContextManager["ITransaction"]):
    """An interface for a database transaction."""


class IAtomic(Protocol):
    def atomic(self) -> ITransaction:
        """
        Opens an atomic block.

        All database operations either all occur, or nothing occurs. Nested atomic
        blocks are allowed, but they will act as no-op.
        """


class IDatabase(IAtomic, Protocol):
    async def __aenter__(self) -> Self:
        return self  # pragma: no cover

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()

    async def shutdown(self) -> None:
        """Performs all necessary actions to shutdown database correctly."""
