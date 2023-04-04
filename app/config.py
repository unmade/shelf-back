from __future__ import annotations

import enum
from datetime import timedelta
from pathlib import Path
from typing import Literal

from pydantic import AnyUrl, BaseModel, BaseSettings, Field, RedisDsn

_MB = 2**20
_GB = 2**30

_BASE_DIR = Path(__file__).absolute().resolve().parent.parent


class StorageType(str, enum.Enum):
    filesystem = "filesystem"
    s3 = "s3"


class AbsPath(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value) -> str:
        if not isinstance(value, str):
            raise TypeError('string required')
        if Path(value).is_absolute():
            return value
        return str(_BASE_DIR / value)

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({super().__repr__()})'


class StringList(list[str]):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value) -> list[str]:
        if isinstance(value, str):
            return value.split(",")
        if not isinstance(value, list):
            raise TypeError('list or string required')
        return value

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({super().__repr__()})'


class AuthConfig(BaseModel):
    secret_key: str
    access_token_ttl: timedelta = timedelta(minutes=15)
    refresh_token_ttl: timedelta = timedelta(minutes=15)


class CacheConfig(BaseModel):
    backend_dsn: Literal["mem://"] | RedisDsn = "mem://"
    disk_cache_max_size: int = _GB


class CeleryConfig(BaseModel):
    backend_dsn: RedisDsn
    broker_dsn: RedisDsn


class CORSConfig(BaseModel):
    allowed_origins: StringList = StringList([])
    allowed_methods: StringList = StringList(["*"])
    allowed_headers: StringList = StringList(["*"])


class EdgeDBConfig(BaseModel):
    dsn: str
    edgedb_tls_ca_file: AbsPath | None = None
    edgedb_tls_security: str | None = None
    edgedb_schema: AbsPath = AbsPath(str(_BASE_DIR / "./dbschema/default.esdl"))
    edgedb_max_concurrency: int | None = None


class FeatureConfig(BaseModel):
    sign_up_disabled: bool = False
    upload_file_max_size: int = 100 * _MB


class FileSystemStorageConfig(BaseModel):
    type: Literal[StorageType.filesystem] = StorageType.filesystem
    quota: int | None = 512 * _MB
    fs_location: str


class S3StorageConfig(BaseModel):
    type: Literal[StorageType.s3] = StorageType.s3
    quota: int | None = 512 * _MB
    s3_location: str
    s3_access_key_id: str
    s3_secret_access_key: str
    s3_bucket: str = "shelf"
    s3_region: str


class SentryConfig(BaseModel):
    dsn: AnyUrl | None = None
    environment: str | None = None


class AppConfig(BaseSettings):
    app_name: str = "Shelf"
    app_version: str = "dev"
    app_debug: bool = False

    auth: AuthConfig
    cache: CacheConfig = CacheConfig()
    cors: CORSConfig = CORSConfig()
    celery: CeleryConfig
    database: EdgeDBConfig
    features: FeatureConfig = FeatureConfig()
    sentry: SentryConfig = SentryConfig()
    storage: FileSystemStorageConfig | S3StorageConfig = Field(discriminator="type")

    class Config:
        env_file = '.env', '.env.prod'
        env_file_encoding = 'utf-8'
        env_nested_delimiter = "__"


config = AppConfig()
