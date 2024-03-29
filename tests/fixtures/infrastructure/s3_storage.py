from __future__ import annotations

import contextlib

import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config import AppConfig, S3StorageConfig
from app.infrastructure.storage.s3 import S3Storage
from app.infrastructure.storage.s3.clients import (
    AsyncS3Client,
    S3ClientConfig,
)
from app.infrastructure.storage.s3.clients.exceptions import BucketAlreadyOwnedByYou


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
    async with AsyncS3Client(
        S3ClientConfig(
            base_url=str(s3_storage_config.s3_location),
            access_key=s3_storage_config.s3_access_key_id,
            secret_key=s3_storage_config.s3_secret_access_key,
            region=s3_storage_config.s3_region,
        )
    ) as client:
        yield client


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
async def s3_storage(
    setup_s3_bucket,
    teardown_s3_bucket,
    teardown_s3_files,
    s3_storage_config: S3StorageConfig
):
    """An instance of `S3Storage` created with a `s3_storage_config`."""
    async with S3Storage(s3_storage_config) as storage:
        yield storage
