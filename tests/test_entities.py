from __future__ import annotations

from pathlib import PurePath
from typing import Optional

import pytest
from faker import Faker

from app import mediatypes
from app.entities import File

fake = Faker()


@pytest.fixture
def file_factory():
    def _file_factory(
        path: Optional[str] = None,
        mediatype: Optional[str] = None,
    ) -> File:
        if path is not None:
            pathname = PurePath(path)
        else:
            pathname = PurePath(fake.file_path(depth=3))

        return File(
            id=str(fake.uuid4()),
            name=pathname.name,
            path=str(pathname),
            size=fake.pyint(),
            mtime=fake.pyfloat(positive=True),
            mediatype=mediatype or fake.mime_type(),
        )

    return _file_factory


def test_compare_two_equal_files(file_factory) -> None:
    a: File = file_factory()
    b = File(
        id=a.id,
        name=a.name,
        path=a.path,
        size=a.size,
        mtime=a.mtime,
        mediatype=a.mediatype,
    )
    assert a == b


def test_compare_two_non_equal_files(file_factory):
    assert file_factory() != file_factory()


def test_comparing_file_with_another_object_always_false(file_factory):
    assert (file_factory() == {}) is False


@pytest.mark.parametrize(["path", "hidden"], [
    ("f.txt", False),
    (".f.txt", True),
])
def test_file_is_hidden(file_factory, path: str, hidden: bool):
    file = file_factory(path)
    assert file.is_hidden() is hidden


@pytest.mark.parametrize(["mediatype", "folder"], [
    (None, False),
    (mediatypes.FOLDER, True),
])
def test_file_is_folder(file_factory, mediatype, folder):
    file = file_factory(mediatype=mediatype)
    assert file.is_folder() is folder
