from __future__ import annotations

from typing import TYPE_CHECKING

import boto3
import pytest
from botocore.client import Config
from botocore.exceptions import ClientError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config import AppConfig, S3StorageConfig
from app.infrastructure.storage.s3 import S3Storage

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3ServiceResource


class _S3StorageConfig(S3StorageConfig, BaseSettings):
    type: str  # type: ignore
    s3_bucket: str = "shelft-test"

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
def s3_resource(s3_storage_config: S3StorageConfig):
    """An s3 resource client."""
    return boto3.resource(
        "s3",
        endpoint_url=s3_storage_config.s3_location,
        aws_access_key_id=s3_storage_config.s3_access_key_id,
        aws_secret_access_key=s3_storage_config.s3_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name=s3_storage_config.s3_region,
    )


@pytest.fixture(scope="session")
def setup_s3_bucket(s3_resource: S3ServiceResource, s3_bucket: str):  # pragma: no cover
    """Setups fixture to create a new bucket."""
    bucket = s3_resource.Bucket(s3_bucket)

    try:
        bucket.create()
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "BucketAlreadyOwnedByYou":
            return
        raise


@pytest.fixture(scope="session")
def teardown_s3_bucket(  # pragma: no cover
    s3_resource: S3ServiceResource, s3_bucket: str
):
    """Teardown fixture to remove all files in the bucket, then remove the bucket."""
    try:
        yield
    finally:
        from botocore.exceptions import ClientError

        bucket = s3_resource.Bucket(s3_bucket)

        try:
            bucket.load()
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                return
            raise

        bucket.objects.delete()
        bucket.delete()


@pytest.fixture
def teardown_s3_files(s3_resource: S3ServiceResource, s3_bucket: str):
    """Teardown fixture to clean up all files in the bucket after each test."""
    try:
        yield
    finally:
        bucket = s3_resource.Bucket(s3_bucket)
        bucket.objects.delete()


@pytest.fixture
def s3_storage(
    setup_s3_bucket,
    teardown_s3_bucket,
    teardown_s3_files,
    s3_storage_config: S3StorageConfig
) -> S3Storage:
    """An instance of `S3Storage` created with an `s3_storage_config`."""
    return S3Storage(s3_storage_config)
