from __future__ import annotations

from io import BytesIO
from typing import IO, BinaryIO, Protocol, Self

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


class InMemoryFileContent:
    __slots__ = ("file", "size")

    def __init__(self, content: bytes):
        self.file: BinaryIO = BytesIO(content)
        self.size = len(content)

    @classmethod
    def from_buffer(cls, content: IO[bytes]) -> Self:
        content.seek(0)
        return cls(content.read())

    async def read(self, size: int = -1) -> bytes:
        return self.file.read(size)

    async def seek(self, offset: int) -> None:
        self.file.seek(offset)

    async def close(self) -> None:
        self.file.close()  # pragma: no cover
