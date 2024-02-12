from __future__ import annotations

import enum
import re
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, Self, TypeAlias
from urllib.parse import urlsplit, urlunsplit

from pydantic import AnyHttpUrl, BaseModel, Field, RedisDsn
from pydantic.functional_validators import AfterValidator, BeforeValidator
from pydantic_core import core_schema
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from pydantic import GetCoreSchemaHandler
    from pydantic_core.core_schema import CoreSchema

_BASE_DIR = Path(__file__).absolute().resolve().parent.parent


class StorageType(str, enum.Enum):
    filesystem = "filesystem"
    s3 = "s3"


class BytesSizeMultipliers(int, enum.Enum):
    gb = 2**30
    mb = 2**20
    kb = 2**10
    b = 1


class ThumbnailSize(enum.IntEnum):
    xs = 72
    lg = 768
    xxl = 2880

    ai = 768


def _as_absolute_path(value: str) -> str | None:
    if value is None:
        return value
    if Path(value).is_absolute():
        return value
    return str(_BASE_DIR / value)


def _parse_bytes_size(value):
    if not isinstance(value, str):
        return value

    value = value.strip().lower()
    if value.isnumeric():
        return int(value)
    if match := re.match(r'^(\d+(?:\.[\d]+)?)([gmk]?b)$', value):
        size, unit = match.groups()
        multiplier = BytesSizeMultipliers[unit]
        return int(float(size) * multiplier)
    raise ValueError('string in a valid format required (e.g. "1KB", "1.5GB")')


def _parse_timedelta_from_str(value):
    if not isinstance(value, str):
        return value

    msg = 'string in a valid format required (e.g. "1d6h30m15s", "2h30m", "15m")'
    value = value.strip().lower()
    pattern = (
        r"((?P<days>\d+)d)?"
        r"((?P<hours>\d+)h)?"
        r"((?P<minutes>\d+)m)?"
        r"((?P<seconds>\d+)s)?"
    )
    match = re.fullmatch(pattern, value)
    if not match:
        raise ValueError(msg)

    items = match.groupdict().items()
    kwargs = {key: int(value)for key, value in items if value}
    if not kwargs:
        raise ValueError(msg)

    return timedelta(**kwargs)


AbsPath = Annotated[str, AfterValidator(_as_absolute_path)]
BytesSize = Annotated[int, BeforeValidator(_parse_bytes_size)]
TTL = Annotated[timedelta, BeforeValidator(_parse_timedelta_from_str)]


class EdgeDBDSN(str):
    __slots__ = ()

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(cls, handler(str))

    @property
    def name(self) -> str:
        """Returns database name."""
        result = urlsplit(str(self))
        return result.path.strip('/')

    @property
    def origin(self) -> str:
        """Return database host."""
        result = urlsplit(str(self))
        return urlunsplit((result.scheme, result.netloc, "", "", ""))

    def with_name(self, name: str) -> Self:
        """Returns a copy of current config with updated database name."""
        scheme, netloc, _, query, fragments = urlsplit(str(self))
        dsn = urlunsplit((scheme, netloc, f"/{name}", query, fragments))
        return self.__class__(dsn)


class AuthConfig(BaseModel):
    secret_key: str
    service_token: str | None = None
    access_token_ttl: TTL = TTL(minutes=15)
    refresh_token_ttl: TTL = TTL(days=3)


class CacheConfig(BaseModel):
    backend_dsn: Literal["mem://"] | RedisDsn = "mem://"
    disk_cache_max_size: BytesSize = BytesSizeMultipliers.gb


class CORSConfig(BaseModel):
    allowed_origins: list[str] = []
    allowed_methods: list[str] = ["*"]
    allowed_headers: list[str] = ["*"]


class EdgeDBConfig(BaseModel):
    dsn: EdgeDBDSN | None = None
    edgedb_tls_ca_file: AbsPath | None = None
    edgedb_tls_security: str | None = None
    edgedb_schema: AbsPath = str(_BASE_DIR / "./dbschema/default.esdl")
    edgedb_max_concurrency: int | None = None

    def with_pool_size(self, size: int) -> Self:
        return self.model_copy(update={"edgedb_max_concurrency": size})


class FeatureConfig(BaseModel):
    max_file_size_to_thumbnail: BytesSize = 20 * BytesSizeMultipliers.mb
    max_image_pixels: int = 89_478_485
    photos_library_path: str = "Photos/Library"
    pre_generated_thumbnail_sizes: set[ThumbnailSize] = {
        ThumbnailSize.xs,
        ThumbnailSize.lg,
        ThumbnailSize.xxl,
        ThumbnailSize.ai,
    }
    sign_up_disabled: bool = False
    upload_file_max_size: BytesSize = 100 * BytesSizeMultipliers.mb


class FileSystemStorageConfig(BaseModel):
    type: Literal[StorageType.filesystem] = StorageType.filesystem
    quota: BytesSize | None = None
    fs_location: str


class IndexerClientConfig(BaseModel):
    url: AnyHttpUrl | None = None
    timeout: float = 10.0


class S3StorageConfig(BaseModel):
    type: Literal[StorageType.s3] = StorageType.s3
    quota: BytesSize | None = None
    s3_location: AnyHttpUrl
    s3_access_key_id: str
    s3_secret_access_key: str
    s3_bucket: str = "shelf"
    s3_region: str


class SentryConfig(BaseModel):
    dsn: Annotated[str | None, RedisDsn] = None
    environment: str | None = None


class ARQWorkerConfig(BaseModel):
    broker_dsn: Annotated[str, RedisDsn]


DatabaseConfig: TypeAlias = EdgeDBConfig

StorageConfig: TypeAlias = Annotated[
    FileSystemStorageConfig | S3StorageConfig,
    Field(discriminator="type")
]

WorkerConfig: TypeAlias = ARQWorkerConfig


class AppConfig(BaseSettings):
    app_name: str = "Shelf"
    app_version: str = "dev"
    app_debug: bool = False

    auth: AuthConfig
    cache: CacheConfig = CacheConfig()
    cors: CORSConfig
    database: DatabaseConfig
    features: FeatureConfig = FeatureConfig()
    indexer: IndexerClientConfig = IndexerClientConfig()
    sentry: SentryConfig = SentryConfig()
    storage: StorageConfig
    worker: WorkerConfig

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.prod", ".env.local"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="allow",
    )


config = AppConfig()
