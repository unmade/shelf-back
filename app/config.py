from __future__ import annotations

import enum
import os
from datetime import timedelta
from pathlib import Path

_MB = 2**20
_GB = 2**30


def _get_bool(key: str) -> bool:
    value = os.getenv(key)
    if value is not None:
        return value.lower() in ["true", "1", "t"]
    return False


def _get_int_or_none(key: str) -> int | None:
    value = os.getenv(key)
    if value is not None:
        return int(value)
    return value


def _get_list(key: str, default: list[str] | None = None) -> list[str]:
    value = os.getenv(key)
    if value is not None:
        return value.split(",")
    if default is not None:
        return default
    return []


def _get_optional_path(key: str, basepath: Path) -> str | None:
    value = os.getenv(key)
    if value is not None:
        return str(basepath / value)
    return value


class StorageType(str, enum.Enum):
    filesystem = "filesystem"
    s3 = "s3"


ACCESS_TOKEN_EXPIRE = timedelta(
    minutes=float(os.getenv("ACCESS_TOKEN_EXPIRE_IN_MINUTES", 15)),
)


APP_NAME = os.getenv("APP_NAME", "Shelf")
APP_DEBUG = _get_bool("APP_DEBUG")
APP_MAX_DOWNLOAD_WITHOUT_STREAMING = int(
    os.getenv(
        "APP_MAX_DOWNLOAD_WITHOUT_STREAMING_IN_BYTES",
        5 * _MB,
    )
)
APP_SECRET_KEY = os.environ["APP_SECRET_KEY"]
APP_VERSION = os.getenv("APP_VERSION", "dev")

BASE_DIR = Path(__file__).absolute().resolve().parent.parent

CACHE_BACKEND_DSN = os.getenv("CACHE_BACKEND_DSN", "mem://")

CELERY_BACKEND_DSN = os.environ["CELERY_BACKEND_DSN"]
CELERY_BROKER_DSN = os.environ["CELERY_BROKER_DSN"]

CLIENT_CACHE_MAX_SIZE = os.getenv("CLIENT_CACHE_MAX_SIZE_IN_BYTES", _GB)

CORS_ALLOW_ORIGINS = _get_list("CORS_ALLOW_ORIGINS")

DATABASE_DSN = os.getenv("DATABASE_DSN")
DATABASE_TLS_CA_FILE = _get_optional_path("DATABASE_TLS_CA_FILE", basepath=BASE_DIR)
DATABASE_TLS_SECURITY = os.getenv("DATABASE_TLS_SECURITY")

FEATURES_SIGN_UP_DISABLED = _get_bool("FEATURES_SIGN_UP_DISABLED")
FEATURES_UPLOAD_FILE_MAX_SIZE = int(
    os.getenv(
        "FEATURES_UPLOAD_FILE_MAX_SIZE_IN_BYTES",
        default=100 * _MB,
    )
)

STORAGE_TYPE = StorageType(os.getenv("STORAGE_TYPE", "filesystem"))
STORAGE_LOCATION = os.environ["STORAGE_LOCATION"]
STORAGE_QUOTA = _get_int_or_none("STORAGE_QUOTA_PER_ACCOUNT_IN_BYTES")

STORAGE_S3_ACCESS_KEY_ID = os.getenv("STORAGE_S3_ACCESS_KEY_ID")
STORAGE_S3_SECRET_ACCESS_KEY = os.getenv("STORAGE_S3_SECRET_ACCESS_KEY")
STORAGE_S3_BUCKET_NAME = os.getenv("STORAGE_S3_BUCKET_NAME", "shelf")
STORAGE_S3_REGION_NAME = os.getenv("STORAGE_S3_REGION_NAME")

SENTRY_DSN = os.getenv("SENTRY_DSN")
SENTRY_ENV = os.getenv("SENTRY_ENV")

TRASH_FOLDER_NAME = "Trash"
