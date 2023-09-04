from __future__ import annotations

from .filesystem import FileSystemStorage
from .s3 import S3Storage

__all__ = [
    "FileSystemStorage",
    "S3Storage",
]
