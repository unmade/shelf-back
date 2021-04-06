from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from typing import Optional


def _get_bool(key: str) -> bool:
    value = os.getenv(key)
    if value is not None:
        return value.lower() in ["true", "1", "t"]
    return False


def _get_list(key: str, default: Optional[list[str]] = None) -> list[str]:
    value = os.getenv(key)
    if value is not None:
        return value.split(",")
    else:
        if default is not None:
            return default
    return []


ACCESS_TOKEN_EXPIRE = timedelta(
    minutes=float(os.getenv("ACCESS_TOKEN_EXPIRE_IN_MINUTES", 15)),
)


APP_NAME = os.getenv("APP_NAME", "Shelf")
APP_DEBUG = _get_bool("APP_DEBUG")
APP_MAX_DOWNLOAD_WITHOUT_STREAMING = int(
    os.getenv(
        "APP_MAX_DOWNLOAD_WITHOUT_STREAMING_IN_BYTES",
        10_485_760,  # Defaults to 10 MB
    )
)
APP_SECRET_KEY = os.environ["APP_SECRET_KEY"]
APP_VERSION = os.getenv("APP_VERSION")

BASE_DIR = Path(__file__).absolute().resolve().parent.parent

CORS_ALLOW_ORIGINS = _get_list("CORS_ALLOW_ORIGINS")

EDGEDB_DSN = os.environ["EDGEDB_DSN"]

STATIC_DIR = Path(os.getenv("STATIC_DIR", "./static"))

TRASH_FOLDER_NAME = "Trash"
