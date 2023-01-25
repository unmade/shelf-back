from __future__ import annotations

from typing import AsyncIterator, Protocol, Self

__all__ = ["IDatabase"]


class IDatabase(Protocol):
    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()

    def atomic(self, *, attempts: int = 3) -> AsyncIterator[None]:
        """
        Opens a retryable atomic block.

        All database operations either all occurs, or nothing occurs. The atomic block
        will attempt to re-execute its body if a transient error occurs, such as a
        network error or a transaction serialization error.

        Nested atomic blocks are allowed, but they will act as no-op.

        Args:
            attempts (int, optional): The default number of attempts. Defaults to 3.

        Returns:
            AsyncIterator[None]: An async iterator without any value.
        """

    async def shutdown(self) -> None:
        """Performs all necessary actions to shutdown database correctly."""
