from __future__ import annotations

import uuid
from pathlib import PurePath

import pytest
from faker import Faker

from app import mediatypes
from app.domain.entities import Fingerprint
from app.entities import File

fake = Faker()


@pytest.fixture
def file_factory():
    def _file_factory(
        path: str | None = None,
        mediatype: str | None = None,
    ) -> File:
        pathname = path or fake.file_path(depth=3)

        return File(
            id=str(fake.uuid4()),
            name=PurePath(pathname).name,
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


def test_compare_two_equal_fingerprints() -> None:
    file_id = uuid.uuid4()
    value = 16493668159829433821
    a = Fingerprint(file_id=file_id, value=value)
    b = Fingerprint(file_id=file_id, value=value)
    assert a == b


def test_compare_two_non_equal_fingerprints() -> None:
    value = 16493668159829433821
    a = Fingerprint(file_id=uuid.uuid4(), value=value)
    b = Fingerprint(file_id=uuid.uuid4(), value=value)
    assert a != b


def test_comparing_fingerprint_with_another_object_always_false() -> None:
    fp = Fingerprint(file_id=uuid.uuid4(), value=16493668159829433821)
    assert (fp == {}) is False


def test_hashes_are_the_same_for_equal_fingerprints() -> None:
    file_id = uuid.uuid4()
    value = 16493668159829433821
    a = Fingerprint(file_id=file_id, value=value)
    b = Fingerprint(file_id=file_id, value=value)
    assert hash(a) == hash(b)


def test_hashes_are_the_different_for_non_equal_fingerprints() -> None:
    value = 16493668159829433821
    a = Fingerprint(file_id=uuid.uuid4(), value=value)
    b = Fingerprint(file_id=uuid.uuid4(), value=value)
    assert hash(a) != hash(b)


def test_fingerprint_representation() -> None:
    file_id = uuid.uuid4()
    value = 16493668159829433821
    fp = Fingerprint(file_id=file_id, value=value)
    assert repr(fp) == f"Fingerprint(file_id='{file_id}', value={value})"
