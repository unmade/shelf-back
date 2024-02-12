from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

__all__ = [
    "IIndexerClient",
]


class IIndexerClient(AbstractAsyncContextManager["IIndexerClient"], Protocol):
    async def track(
        self,
        file_id: UUID,
        storage_path: str,
        file_name: str,
        user_id: UUID,
    ) -> None:
        """Adds file to the index."""
