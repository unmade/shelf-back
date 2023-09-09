from __future__ import annotations

from typing import BinaryIO, Protocol

__all__ = ["IFileContent"]


class IFileContent(Protocol):
    size: int
    file: BinaryIO

    async def read(self, size: int = -1) -> bytes:
        ...

    async def seek(self, offset: int) -> None:
        ...

    async def close(self) -> None:
        ...
