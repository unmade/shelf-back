from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contextvars import ContextVar

    from gel.asyncio_client import AsyncIOClient, AsyncIOIteration

    type GelTransaction = AsyncIOIteration
    type GelAnyConn = AsyncIOClient | AsyncIOIteration
    type GelContext = ContextVar[AsyncIOClient | AsyncIOIteration]
