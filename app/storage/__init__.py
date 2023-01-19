from __future__ import annotations

from typing import TYPE_CHECKING

from app import config

if TYPE_CHECKING:
    from .base import Storage


def _get_storage_class(storage_type: config.StorageType) -> type[Storage]:
    """Return storage class based on STORAGE_TYPE environment variable."""
    if storage_type == config.StorageType.filesystem:
        from .filesystem import FileSystemStorage

        return FileSystemStorage

    if storage_type == config.StorageType.s3:
        from .s3 import S3Storage

        return S3Storage

    raise ValueError(f"Unknown storage type: {storage_type}")


storage = _get_storage_class(config.STORAGE_TYPE)(config.STORAGE_LOCATION)
