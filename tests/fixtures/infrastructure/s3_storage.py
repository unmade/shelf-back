from __future__ import annotations

import contextlib

import httpx
import pytest
from aioaws.s3 import S3Config
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config import AppConfig, S3StorageConfig
from app.infrastructure.storage.async_s3 import AsyncS3Storage
from app.infrastructure.storage.async_s3.client import (
    AsyncS3Client,
    BucketAlreadyOwnedByYou,
)


class _S3StorageConfig(S3StorageConfig, BaseSettings):
    type: str  # type: ignore
    s3_bucket: str = "shelf-test"

    model_config = SettingsConfigDict(
        extra="ignore",
    )


class _AppConfig(AppConfig):
    storage: _S3StorageConfig


@pytest.fixture(scope="session")
def s3_storage_config():
    """An S3StorageConfig config with `tmp_path` as location."""
    return _AppConfig().storage


@pytest.fixture(scope="session")
def s3_bucket(s3_storage_config: S3StorageConfig):
    return s3_storage_config.s3_bucket


@pytest.fixture(scope="session")
async def s3_client(s3_storage_config: S3StorageConfig):
    """An s3 client."""
    config = s3_storage_config
    netloc = ":".join([str(config.s3_location.host), str(config.s3_location.port)])
    async with httpx.AsyncClient() as client:
        s3 = AsyncS3Client(
            client,
            S3Config(
                aws_host=netloc,
                aws_access_key=config.s3_access_key_id,
                aws_secret_key=config.s3_secret_access_key,
                aws_region=config.s3_region,
                aws_s3_bucket=config.s3_bucket,
            ),
        )
        s3._aws_client.schema = config.s3_location.scheme
        yield s3


@pytest.fixture(scope="session")
async def setup_s3_bucket(s3_client: AsyncS3Client, s3_bucket: str):  # pragma: no cover
    """Setups fixture to create a new bucket."""
    with contextlib.suppress(BucketAlreadyOwnedByYou):
        await s3_client.create_bucket(s3_bucket)


@pytest.fixture(scope="session")
async def teardown_s3_bucket(  # pragma: no cover
    s3_client: AsyncS3Client, s3_bucket: str
):
    """Teardown fixture to remove all files in the bucket, then remove the bucket."""
    try:
        yield
    finally:
        await s3_client.delete_recursive(s3_bucket, prefix=None)
        await s3_client.delete_bucket(s3_bucket)


@pytest.fixture
async def teardown_s3_files(s3_client: AsyncS3Client, s3_bucket: str):
    """Teardown fixture to clean up all files in the bucket after each test."""
    try:
        yield
    finally:
        await s3_client.delete_recursive(s3_bucket, prefix=None)


@pytest.fixture
def async_s3_storage(
    setup_s3_bucket,
    teardown_s3_bucket,
    teardown_s3_files,
    s3_storage_config: S3StorageConfig
) -> AsyncS3Storage:
    """An instance of `S3Storage` created with a `s3_storage_config`."""
    return AsyncS3Storage(s3_storage_config)
