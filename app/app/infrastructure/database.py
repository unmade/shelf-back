from __future__ import annotations

from typing import AsyncIterator, Protocol

__all__ = ["IDatabase"]


class IDatabase(Protocol):
    def atomic(self, *, attempts: int = 3) -> AsyncIterator[None]:
        """
        Open a retryable atomic block.

        All database operations either all occurs, or nothing occurs. The atomic block
        will attempt to re-execute its body if a transient error occurs, such as a
        network error or a transaction serialization error.

        Nested atomic blocks are allowed, but they will act as no-op.

        Args:
            attempts (int, optional): The default number of attempts. Defaults to 3.

        Returns:
            AsyncIterator[None]: An async iterator without any value.
        """
