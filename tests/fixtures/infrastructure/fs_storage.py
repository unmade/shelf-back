from pathlib import Path

import pytest

from app.config import FileSystemStorageConfig
from app.infrastructure.storage.filesystem import FileSystemStorage


@pytest.fixture
def fs_storage_config(tmp_path: Path) -> FileSystemStorageConfig:
    """A FileSystemStorage config with `tmp_path` as location."""
    return FileSystemStorageConfig(fs_location=str(tmp_path))


@pytest.fixture
def fs_storage(fs_storage_config: FileSystemStorageConfig) -> FileSystemStorage:
    """An instance of FileSystemStorage with `tmp_path` fixture as a location."""
    return FileSystemStorage(fs_storage_config)
