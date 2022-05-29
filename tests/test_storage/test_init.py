from __future__ import annotations

from typing import TYPE_CHECKING, Type

import pytest

from app.config import StorageType
from app.storage import _get_storage_class
from app.storage.filesystem import FileSystemStorage
from app.storage.s3 import S3Storage

if TYPE_CHECKING:
    from app.storage.base import Storage


@pytest.mark.parametrize(["storage_type", "storage_class"], [
    (StorageType.filesystem, FileSystemStorage),
    (StorageType.s3, S3Storage),
])
def test_get_storage_class(storage_type: StorageType, storage_class: Type[Storage]):
    """Test that the correct storage class is returned."""
    assert _get_storage_class(storage_type) is storage_class


def test_get_storage_class_with_unknown_type():
    """Test that ValueError is raised when an unknown storage type is passed."""
    with pytest.raises(ValueError) as excinfo:
        _get_storage_class("unknown")  # type: ignore

    assert str(excinfo.value) == "Unknown storage type: unknown"
