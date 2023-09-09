from __future__ import annotations

from importlib import resources
from io import BytesIO
from typing import IO, TYPE_CHECKING, BinaryIO, Self

import pytest
from PIL import Image

if TYPE_CHECKING:
    from app.app.files.domain import IFileContent


class FileContent:
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
        self.file.close()


@pytest.fixture
def content() -> IFileContent:
    """A sample file content."""
    return FileContent(b"I'm a Dummy File!")


@pytest.fixture
def image_content() -> IFileContent:
    """Create a sample in-memory image."""
    buffer = BytesIO()
    with Image.new("RGB", (256, 256)) as im:
        im.save(buffer, "JPEG")
    return FileContent.from_buffer(buffer)


@pytest.fixture
def image_content_with_exif() -> IFileContent:
    name = "exif_iphone_with_hdr_on.jpeg"
    buffer = BytesIO(resources.files("tests.data.images").joinpath(name).read_bytes())
    return FileContent.from_buffer(buffer)
