from __future__ import annotations

from typing import TYPE_CHECKING

from app import config

from .filesystem import FileSystemStorage

if TYPE_CHECKING:
    from .base import Storage


storage: Storage = FileSystemStorage(config.STORAGE_LOCATION)
