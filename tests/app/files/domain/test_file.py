from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from faker import Faker

from app.app.files.domain import File, Path, mediatypes

if TYPE_CHECKING:
    from app.app.files.domain.path import AnyPath

fake = Faker()


def _make_file(
    ns_path: str | None = None,
    path: AnyPath | None = None,
    mediatype: str | None = None,
) -> File:
    pathname = path or fake.file_path(depth=3)

    return File(
        id=fake.uuid4(),
        ns_path=ns_path or fake.file_path(depth=1),
        name=Path(pathname).name,
        path=Path(pathname),
        chash=uuid.uuid4().hex,
        size=fake.pyint(),
        mtime=fake.pyfloat(positive=True),
        mediatype=mediatype or fake.mime_type(),
    )


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
