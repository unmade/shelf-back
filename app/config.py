import os
from pathlib import Path


def _get_bool(key: str) -> bool:
    value = os.getenv(key)
    if value is not None:
        return value.lower() in ["true", "1", "t"]
    return False


ACCESS_TOKEN_EXPIRE_MINUTES = 15

APP_NAME = os.getenv("APP_NAME", "Shelf")
APP_DEBUG = _get_bool("APP_DEBUG")
APP_SECRET_KEY = os.environ["APP_SECRET_KEY"]
APP_VERSION = os.getenv("APP_VERSION")

DATABASE_DSN = os.environ["DATABASE_DSN"]

STATIC_DIR = Path(os.getenv("STATIC_DIR", "./static"))

TRASH_FOLDER_NAME = "Trash"
