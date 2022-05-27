from __future__ import annotations

import pytest

from app.storage.base import StorageFile


@pytest.fixture()
def storage_file() -> StorageFile:
    """A simple instance of a storage file."""
    return StorageFile(
        name="f.txt",
        ns_path="user",
        path="a/f.txt",
        size=8,
        mtime=1628154987,
        is_dir=False,
    )


def test_storage_file_string_representation(storage_file: StorageFile):
    assert str(storage_file) == "user:a/f.txt"


def test_storage_file_representation(storage_file: StorageFile):
    assert repr(storage_file) == (
        "StorageFile("
        "name='f.txt', "
        "ns_path='user', "
        "path='a/f.txt', "
        "size=8, "
        "mtime=1628154987, "
        "is_dir=False"
        ")"
    )
