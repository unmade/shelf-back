from __future__ import annotations

import pytest
from faker import Faker

from app.app.files.domain import File, Path, mediatypes

fake = Faker()


def _make_file(
    path: str | None = None,
    mediatype: str | None = None,
    ns_path: str | None = None,
) -> File:
    pathname = path or fake.file_path(depth=3)

    return File(
        id=str(fake.uuid4()),
        ns_path=ns_path or fake.file_path(depth=1),
        name=Path(pathname).name,
        path=str(pathname),
        size=fake.pyint(),
        mtime=fake.pyfloat(positive=True),
        mediatype=mediatype or fake.mime_type(),
    )


class TestFileEQ:
    def test_equal_files(self) -> None:
        a = _make_file()
        b = File(
            id=a.id,
            ns_path=a.ns_path,
            name=a.name,
            path=a.path,
            size=a.size,
            mtime=a.mtime,
            mediatype=a.mediatype,
        )
        assert a == b

    def test_two_non_equal_files(self):
        assert _make_file() != _make_file()

    def test_comparing_file_with_another_object_always_false(self):
        assert (_make_file() == {}) is False


class TestRepr:
    def test(self):
        file = _make_file(ns_path="admin", path="home")
        assert repr(file) == "<File ns_path='admin' path='home'>"


class TestJson:
    def test(self) -> None:
        file = _make_file()
        assert file.json()


class TestIsHidden:
    @pytest.mark.parametrize(["path", "hidden"], [
        ("f.txt", False),
        (".f.txt", True),
    ])
    def test_file_is_hidden(self, path: str, hidden: bool):
        file = _make_file(path=path)
        assert file.is_hidden() is hidden


class TestIsFolder:
    @pytest.mark.parametrize(["mediatype", "folder"], [
        (None, False),
        (mediatypes.FOLDER, True),
    ])
    def test_file_is_folder(self, mediatype: str | None, folder: bool):
        file = _make_file(mediatype=mediatype)
        assert file.is_folder() is folder
