from __future__ import annotations

from typing import BinaryIO, Protocol

__all__ = ["IFileContent"]


class IFileContent(Protocol):
    size: int
    file: BinaryIO

    async def read(self, size: int = -1) -> bytes:
        """
        Read and return up to size bytes. If the argument is omitted negative,
        data is read and returned until EOF is reached.
        """

    async def seek(self, offset: int) -> None:
        """Change the stream position to the given byte offset."""

    async def close(self) -> None:
        """Flush and close this stream."""
