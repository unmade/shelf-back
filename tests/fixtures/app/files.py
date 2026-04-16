from __future__ import annotations

from importlib import resources
from io import BytesIO
from typing import TYPE_CHECKING, Protocol

import pytest
from PIL import Image

from app.app.blobs.domain.content import InMemoryBlobContent

if TYPE_CHECKING:
    from app.app.blobs.domain import IBlobContent

    class ContentFactory(Protocol):
        def __call__(self, value: bytes = b"I'm Dummy File!") -> IBlobContent:
            ...


@pytest.fixture
def content_factory() -> ContentFactory:
    """A FileContent factory."""
    def factory(value: bytes = b"I'm a Dummy File!") -> IBlobContent:
        return InMemoryBlobContent(value)
    return factory


@pytest.fixture
def content(content_factory: ContentFactory) -> IBlobContent:
    """A sample file content."""
    return content_factory()


@pytest.fixture
def image_content() -> IBlobContent:
    """Create a sample in-memory image."""
    buffer = BytesIO()
    with Image.new("RGB", (256, 256)) as im:
        im.save(buffer, "JPEG")
    return InMemoryBlobContent.from_buffer(buffer)


@pytest.fixture
def image_content_with_exif() -> IBlobContent:
    name = "exif_iphone_with_hdr_on.jpeg"
    buffer = BytesIO(resources.files("tests.data.images").joinpath(name).read_bytes())
    return InMemoryBlobContent.from_buffer(buffer)


@pytest.fixture
def svg_content() -> IBlobContent:
    name = "sample.svg"
    buffer = BytesIO(resources.files("tests.data.images").joinpath(name).read_bytes())
    return InMemoryBlobContent.from_buffer(buffer)
