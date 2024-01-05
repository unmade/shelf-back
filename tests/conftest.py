from __future__ import annotations

import pytest
from faker import Faker

fake = Faker()

pytest_plugins = [
    "pytester",
    "tests.fixtures.app.files",
    "tests.fixtures.infrastructure.arq_worker",
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
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def reuse_db(pytestconfig):
    """
    Returns whether or not to re-use an existing database and to keep it after
    the test run.
    """
    return pytestconfig.getoption("reuse_db", False)
