from __future__ import annotations

import asyncio
from importlib import resources
from io import BytesIO

import pytest
from faker import Faker
from PIL import Image

from app.tasks import CeleryConfig

fake = Faker()

pytest_plugins = [
    "pytester",
    "tests.fixtures.infrastructure.edgedb",
    "tests.fixtures.infrastructure.fs_storage",
    "tests.fixtures.infrastructure.s3_storage",
]


def pytest_addoption(parser):
    parser.addoption(
        "--reuse-db",
        action="store_true",
        default=False,
        help=(
            "whether to keep db after the test run or drop it. "
            "If the database does not exists it will be created"
        ),
    )


@pytest.fixture(scope="session")
def event_loop():
    """Redefine pytest-asyncio event_loop fixture with 'session' scope."""
    loop = asyncio.get_event_loop_policy().get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def reuse_db(pytestconfig):
    """
    Returns whether or not to re-use an existing database and to keep it after
    the test run.
    """
    return pytestconfig.getoption("reuse_db", False)


@pytest.fixture(scope='session')
def celery_config():
    return {
        "broker_url": CeleryConfig.broker_url,
        "result_backend": CeleryConfig.result_backend,
        "result_serializer": CeleryConfig.result_serializer,
        "event_serializer": CeleryConfig.event_serializer,
        "accept_content": CeleryConfig.accept_content,
        "result_accept_content": CeleryConfig.result_accept_content,
    }


@pytest.fixture
def image_content() -> BytesIO:
    """Create a sample in-memory image."""
    buffer = BytesIO()
    with Image.new("RGB", (256, 256)) as im:
        im.save(buffer, "JPEG")
    buffer.seek(0)
    return buffer


@pytest.fixture
def image_content_with_exif() -> BytesIO:
    name = "exif_iphone_with_hdr_on.jpeg"
    return BytesIO(resources.files("tests.data.images").joinpath(name).read_bytes())
