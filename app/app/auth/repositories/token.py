from __future__ import annotations

from typing import Protocol

__all__ = ["ITokenRepository"]


class ITokenRepository(Protocol):
    async def delete(self, key: str) -> str:
        ...

    async def get(self, key: str) -> str:
        ...

    async def set(self, key: str, value: str) -> str:
        ...
