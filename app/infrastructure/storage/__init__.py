from __future__ import annotations

from typing import TYPE_CHECKING

from app import config

from .filesystem import FileSystemStorage
from .s3 import S3Storage

__all__ = [
    "FileSystemStorage",
    "S3Storage",
]

if TYPE_CHECKING:
    from app.app.infrastructure.storage import IStorage


def _get_storage_class(storage_type: config.StorageType) -> type[IStorage]:
    """Return storage class based on STORAGE_TYPE environment variable."""
    if storage_type == config.StorageType.filesystem:
        return FileSystemStorage

    if storage_type == config.StorageType.s3:
        return S3Storage

    raise ValueError(f"Unknown storage type: {storage_type}")


storage = _get_storage_class(config.STORAGE_TYPE)(config.STORAGE_LOCATION)
