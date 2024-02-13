from __future__ import annotations

from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Self

from httpx import AsyncClient

if TYPE_CHECKING:
    from uuid import UUID

    from app.config import IndexerClientConfig

__all__ = [
    "IndexerClient",
]


class IndexerClient:
    __slots__ = ("_stack", "client", )

    def __init__(self, config: IndexerClientConfig):
        assert config.url is not None, "`url` can't be empty"
        self.client = AsyncClient(
            base_url=str(config.url),
            timeout=config.timeout,
            http2=True,
        )
        self._stack = AsyncExitStack()

    async def __aenter__(self) -> Self:
        await self._stack.enter_async_context(self.client)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._stack.aclose()

    async def track(
        self,
        file_id: UUID,
        storage_path: str,
        file_name: str,
        user_id: UUID,
    ) -> None:
        await self.client.post(
            "/api/photos/process",
            json={
                "file_id": str(file_id),
                "storage_path": storage_path,
                "file_name": file_name,
                "owner": str(user_id),
            }
        )
