from __future__ import annotations

import pytest

from app.api.files.exceptions import FileAlreadyDeleted, MalformedPath
from app.api.files.schemas import MoveRequest, MoveToTrashRequest, _normalize


class TestNormalize:
    def test(self):
        assert _normalize("some/path") == "some/path"
        assert _normalize(" some/path ") == "some/path"
        assert _normalize(".") == "."

    def test_empty_test(self):
        with pytest.raises(MalformedPath) as excinfo:
            assert _normalize("") == "."
        assert str(excinfo.value) == "Path should not be empty"

    @pytest.mark.parametrize(["path", "symbol"], [
        ("../Downloads", ".."),
        ("~/.zshrc", "~"),
        ("/Users/admin/Library", "/"),
    ])
    def test_when_path_is_malformed(self, path: str, symbol: str):
        with pytest.raises(MalformedPath) as excinfo:
            _normalize(path)
        assert str(excinfo.value) == f"Path should not start with '{symbol}'"


class TestMoveRequest:
    def test(self):
        schema = MoveRequest(from_path="home/docs", to_path="home/Documents")
        assert schema.from_path == "home/docs"
        assert schema.to_path == "home/Documents"

    @pytest.mark.parametrize(["from_path", "to_path"], [
        (".", "home"),
        ("home", "."),
        ("Trash", "Trashbin"),
        ("Trashbin", "Trash"),
    ])
    def test_when_moving_home_or_trash_folder(self, from_path: str, to_path: str):
        with pytest.raises(MalformedPath) as excinfo:
            MoveRequest(from_path=from_path, to_path=to_path)
        assert str(excinfo.value) == "Can't move Home or Trash folder"

    def test_when_moving_file_to_trash(self):
        with pytest.raises(MalformedPath) as excinfo:
            MoveRequest(from_path="f.txt", to_path="Trash/f.txt")
        assert str(excinfo.value) == "Can't move files inside Trash"

    def test_when_moving_to_itself(self):
        with pytest.raises(MalformedPath) as excinfo:
            MoveRequest(from_path="home/folder", to_path="home/folder/itself")
        assert str(excinfo.value) == "'to_path' should not start with 'from_path'"


class TestMoveToTrashRequest:
    def test_moving_trash(self):
        with pytest.raises(MalformedPath) as excinfo:
            MoveToTrashRequest(path="Trash")
        assert str(excinfo.value) == "Can't move Trash into itself"

    def test_moving_already_trashed_file(self):
        with pytest.raises(FileAlreadyDeleted):
            MoveToTrashRequest(path="Trash/f.txt")
