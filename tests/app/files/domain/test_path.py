from __future__ import annotations

from pathlib import PurePath

import pytest

from app.app.files.domain.path import Path


class TestInit:
    def test_path_is_normalized(self):
        path = Path("a//b/../c")
        assert path._path == "a/c"

    def test_from_itself(self):
        path = Path(Path("a/b"))
        assert path._path == "a/b"


class TestComparison:
    def test_gt(self):
        assert Path("b") > Path("a")
        assert Path("b") > Path("A")
        assert not Path("a") > Path("b")

    def test_ge(self):
        assert Path("a") >= Path("a")
        assert Path("b") >= Path("a")
        assert not Path("a") >= Path("b")

    def test_lt(self):
        assert Path("a") < Path("b")
        assert not Path("b") < Path("a")

    def test_le(self):
        assert Path("a") <= Path("a")
        assert Path("a") <= Path("b")
        assert not Path("b") <= Path("a")

    def test_comparing_with_other_types(self):
        with pytest.raises(TypeError):
            assert not Path("a") > object()
        with pytest.raises(TypeError):
            assert not Path("a") >= object()
        with pytest.raises(TypeError):
            assert not Path("b") < object()
        with pytest.raises(TypeError):
            assert not Path("a") <= object()


class TestEQ:
    def test_case_insensitiveness(self):
        path = Path("a/B/c")
        assert path == Path("a/b/c")
        assert path == "a/b/c"
        assert path == PurePath("a/b/c")

    def test_with_an_arbitrary_object(self):
        path = Path("a/b/c")
        assert path != object()


class TestHash:
    def test(self):
        path_a = Path("a/b")
        path_b = Path("a/b/c")
        paths = {path_a}
        assert path_a in paths
        assert "a/b" not in paths
        assert path_b not in paths

    def test_case_insensitiveness(self):
        path = Path("A/B")
        paths = {path}
        assert Path("a/b") in paths
        assert Path("a/B") in paths


class TestRepr:
    def test(self):
        path = Path("a/b")
        assert repr(path) == "Path('a/b')"


class TestStr:
    def test(self):
        assert str(Path("a/B")) == "a/B"


class TestJoinPath:
    @pytest.mark.parametrize(["left", "right", "result"], [
        (Path("a/b"), Path("c"), Path("a/b/c")),
        (Path("a/b"), "c", Path("a/b/c")),
        (Path("a/b"), PurePath("c"), Path("a/b/c")),
    ])
    def test_left_op(self, left: Path, right: str | Path | PurePath, result: Path):
        path = left / right
        assert isinstance(path, Path)
        assert path == result

    def test_left_op_with_an_arbitrary_object(self):
        with pytest.raises(TypeError):
            Path("a/b") / object()

    @pytest.mark.parametrize(["left", "right", "result"], [
        (Path("a/b"), Path("c"), Path("a/b/c")),
        ("a/b", Path("c"), Path("a/b/c")),
        (PurePath("a/b"), Path("c"), Path("a/b/c")),
    ])
    def test_right_op(self, left: Path, right: str | Path | PurePath, result: Path):
        path = left / right
        assert isinstance(path, Path)
        assert path == result

    def test_right_op_with_an_arbitrary_object(self):
        with pytest.raises(TypeError):
            object() / Path("a/b")


class TestName:
    @pytest.mark.parametrize(["path", "name"], [
        ("a/b/c", "c"),
        ("f.txt", "f.txt"),
        ("a/f.txt", "f.txt"),
    ])
    def test(self, path: str, name: str):
        assert Path(path).name == name
        assert isinstance(Path(path).name, str)


class TestParent:
    @pytest.mark.parametrize(["path", "parent"], [
        ("a/b/c", "a/b"),
        ("f.txt", "."),
        ("a/f.txt", "a"),
    ])
    def test(self, path: str, parent: str):
        assert Path(path).parent == parent


class TestParents:
    def test(self):
        path = Path("a/b/c/f.txt")
        assert list(path.parents) == list(PurePath(str(path)).parents)


class TestStem:
    @pytest.mark.parametrize(["path", "stem"], [
        ("f.txt", "f"),
        ("a/f.tar.gz", "f"),
        ("photo_2023-03-30 23.30.09.jpg", "photo_2023-03-30 23.30.09")
    ])
    def test(self, path: str, stem: str):
        assert Path(path).stem == stem


class TestSuffix:
    @pytest.mark.parametrize(["path", "suffix"], [
        ("f.txt", ".txt"),
        ("a/f.tar.gz", ".tar.gz"),
        ("photo_2023-03-30 23.30.09.jpg", ".jpg")
    ])
    def test(self, path: str, suffix: str):
        assert Path(path).suffix == suffix


class TestIsRelativeTo:
    def test(self):
        path = Path("trashed/folder")
        assert not path.is_relative_to("trash")
        assert path.is_relative_to("trashed")
        assert path.is_relative_to("trashed/folder")
        assert path.is_relative_to(".")


class TestWithRestoredCasing:
    @pytest.mark.parametrize(["target", "source", "expected"], [
        ("docs/folder/file.txt", "Docs/Folder/File.txt", "Docs/Folder/File.txt"),
        ("docs/folder/file.txt", ".", "docs/folder/file.txt"),
    ])
    def test(self, target: str, source: str, expected: str):
        result = Path(target).with_restored_casing(source)
        assert result == expected

    def test_when_path_is_not_relative(self):
        with pytest.raises(ValueError) as excinfo:
            Path("home").with_restored_casing("Trash")
        msg = "Provided path must be relative to the target path."
        assert str(excinfo.value) == msg


class TestWithStem:
    @pytest.mark.parametrize(["path", "stem", "expected"], [
        ("f.txt", "plain", "plain.txt"),
        ("a/f.tar.gz", "dump", "a/dump.tar.gz")
    ])
    def test(self, path: str, stem: str, expected: str):
        result = Path(path).with_stem(stem)
        assert result == expected
