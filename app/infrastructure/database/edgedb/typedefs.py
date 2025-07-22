from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from contextvars import ContextVar

    from gel.asyncio_client import AsyncIOClient, AsyncIOIteration

    EdgeDBTransaction = AsyncIOIteration
    EdgeDBAnyConn: TypeAlias = AsyncIOClient | AsyncIOIteration
    EdgeDBContext = ContextVar[AsyncIOClient | AsyncIOIteration]
