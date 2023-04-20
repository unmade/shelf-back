from __future__ import annotations

import enum
import re
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Literal, Self, TypeAlias
from urllib.parse import urlsplit, urlunsplit

from pydantic import AnyUrl, BaseModel, BaseSettings, Field, RedisDsn

_BASE_DIR = Path(__file__).absolute().resolve().parent.parent


class StorageType(str, enum.Enum):
    filesystem = "filesystem"
    s3 = "s3"


class AbsPath(str):
    __slots__ = ()

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


class BytesSize(int):
    __slots__ = ()

    multipliers = {
        "gb": 2**30,
        "mb": 2**20,
        "kb": 2**10,
    }

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            return cls.from_string(value)
        raise TypeError("string or integer required")

    @classmethod
    def from_string(cls, value: str) -> int:
        value = value.strip().lower()
        if value.isnumeric():
            return int(value)
        if match := re.match(r'^(\d+(?:\.[\d]+)?)([gmk]?b)$', value):
            size, unit = match.groups()
            multiplier = cls.multipliers.get(unit, 1)
            return int(float(size) * multiplier)
        raise ValueError('string in a valid format required (e.g. "1KB", "1.5GB")')

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({super().__repr__()})'


class EdgeDBDSN(AnyUrl):
    __slots__ = ()

    allowed_schemes = {"edgedb"}

    @property
    def name(self) -> str:
        """Returns database name."""
        result = urlsplit(self)
        return result.path.strip('/')

    @property
    def origin(self) -> str:
        """Return database host."""
        result = urlsplit(self)
        return urlunsplit((result.scheme, result.netloc, "", "", ""))

    def with_name(self, name: str) -> Self:
        """Returns a copy of current config with updated database name."""
        scheme, netloc, _, query, fragments = urlsplit(self)
        dsn = urlunsplit((scheme, netloc, f"/{name}", query, fragments))
        return self.__class__(dsn, scheme=scheme)  # type: ignore[no-any-return]


class StringList(list[str]):
    __slots__ = ()

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value) -> list[str]:
        if isinstance(value, str):
            return value.split(",")
        if isinstance(value, list):
            return value
        raise TypeError('list or string required')

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({super().__repr__()})'


class TTL(timedelta):
    __slots__ = ()

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value) -> timedelta:
        if isinstance(value, timedelta):
            return value
        if isinstance(value, str):
            return cls.from_string(value)
        raise TypeError("string or timedelta required")

    @classmethod
    def from_string(cls, value) -> timedelta:
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


class AuthConfig(BaseModel):
    secret_key: str
    access_token_ttl: TTL = TTL(minutes=15)
    refresh_token_ttl: TTL = TTL(days=3)


class CacheConfig(BaseModel):
    backend_dsn: Literal["mem://"] | RedisDsn = "mem://"
    disk_cache_max_size: BytesSize = BytesSize(BytesSize.multipliers["gb"])


class CORSConfig(BaseModel):
    allowed_origins: StringList = StringList([])
    allowed_methods: StringList = StringList(["*"])
    allowed_headers: StringList = StringList(["*"])


class EdgeDBConfig(BaseModel):
    dsn: EdgeDBDSN | None = None
    edgedb_tls_ca_file: AbsPath | None = None
    edgedb_tls_security: str | None = None
    edgedb_schema: AbsPath = AbsPath(str(_BASE_DIR / "./dbschema/default.esdl"))
    edgedb_max_concurrency: int | None = None

    def with_pool_size(self, size: int) -> Self:
        return self.copy(update={"edgedb_max_concurrency": size})


class FeatureConfig(BaseModel):
    sign_up_disabled: bool = False
    upload_file_max_size: BytesSize = BytesSize(100 * BytesSize.multipliers["mb"])


class FileSystemStorageConfig(BaseModel):
    type: Literal[StorageType.filesystem] = StorageType.filesystem
    quota: BytesSize | None = None
    fs_location: str


class S3StorageConfig(BaseModel):
    type: Literal[StorageType.s3] = StorageType.s3
    quota: BytesSize | None = None
    s3_location: str
    s3_access_key_id: str
    s3_secret_access_key: str
    s3_bucket: str = "shelf"
    s3_region: str


class SentryConfig(BaseModel):
    dsn: AnyUrl | None = None
    environment: str | None = None


class ARQWorkerConfig(BaseModel):
    broker_dsn: RedisDsn


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
    cors: CORSConfig = CORSConfig()
    database: DatabaseConfig
    features: FeatureConfig = FeatureConfig()
    sentry: SentryConfig = SentryConfig()
    storage: StorageConfig
    worker: WorkerConfig

    class Config:
        env_file = ".env", ".env.prod"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"


config = AppConfig()
