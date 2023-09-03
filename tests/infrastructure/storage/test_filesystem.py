from __future__ import annotations

import operator
import shutil
from io import BytesIO
from pathlib import Path
from typing import IO, TYPE_CHECKING
from zipfile import ZipFile

import pytest
from asgiref.sync import sync_to_async

from app.app.files.domain import File
from app.infrastructure.storage import FileSystemStorage

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath

pytestmark = [pytest.mark.asyncio]


@pytest.fixture
def file_factory(tmp_path: Path):
    """
    A file factory for a FileSystemStorage.

    Save file in a specified path with a given content and return full path.
    Any missing parents will be created.
    """
    @sync_to_async
    def create_file(
        path: AnyPath,
        content: IO[bytes] = BytesIO(b"I'm Dummy File!"),
    ) -> Path:
        fullpath = Path(str(tmp_path / path))
        fullpath.parent.mkdir(parents=True, exist_ok=True)
        if str(path)[-1] == "/":
            return fullpath
        with open(fullpath, 'wb') as buffer:
            shutil.copyfileobj(content, buffer)

        return fullpath

    return create_file


async def test_delete(file_factory, fs_storage: FileSystemStorage):
    fullpath = await file_factory("user/f.txt")
    assert fullpath.exists()
    await fs_storage.delete("user", "f.txt")
    assert not fullpath.exists()


async def test_delete_but_it_is_a_dir(file_factory, fs_storage: FileSystemStorage):
    fullpath = await file_factory("user/a/f.txt")
    await fs_storage.delete("user", "a")
    assert fullpath.exists()


async def test_delete_but_file_does_not_exist(fs_storage: FileSystemStorage):
    await fs_storage.delete("user", "f.txt")


async def test_deletedir(file_factory, fs_storage: FileSystemStorage):
    fullpath = await file_factory("user/a/f.txt")
    assert fullpath.exists()
    await fs_storage.deletedir("user", "a")
    assert not fullpath.exists()
    assert not fullpath.parent.exists()


async def test_deletedir_but_it_is_a_file(file_factory, fs_storage: FileSystemStorage):
    fullpath = await file_factory("user/a/f.txt")
    await fs_storage.deletedir("user", "a/f.txt")
    assert fullpath.exists()


async def test_deletedir_but_dir_does_not_exist(fs_storage: FileSystemStorage):
    await fs_storage.deletedir("user", "a")


async def test_emptydir(file_factory, fs_storage: FileSystemStorage):
    file_a = await file_factory("user/a/f.txt")
    file_b = await file_factory("user/a/b/f.txt")
    await fs_storage.emptydir("user", "a")
    assert file_a.parent.exists()
    assert not file_a.exists()
    assert not file_b.exists()


async def test_emptydir_but_it_is_a_file(file_factory, fs_storage: FileSystemStorage):
    fullpath = await file_factory("user/a/f.txt")
    await fs_storage.emptydir("user", "a/f.txt")
    assert fullpath.exists()


async def test_emptydir_but_dir_does_not_exist(fs_storage: FileSystemStorage):
    await fs_storage.emptydir("user", "a")


class TestDownload:
    async def test(self, file_factory, fs_storage: FileSystemStorage):
        # GIVEN
        await file_factory("user/f.txt")
        # WHEN
        chunks = fs_storage.download("user", "f.txt")
        # THEN
        content = BytesIO(b"".join([chunk async for chunk in chunks]))
        assert content.read() == b"I'm Dummy File!"

    @pytest.mark.skip("figure out how to handle errors in the async iterator")
    async def test_when_it_is_a_dir(self, file_factory, fs_storage: FileSystemStorage):
        await file_factory("user/a/f.txt")
        with pytest.raises(File.NotFound):
            fs_storage.download("user", "a")

    @pytest.mark.skip("figure out how to handle errors in the async iterator")
    async def test_when_file_does_not_exist(self, fs_storage: FileSystemStorage):
        with pytest.raises(File.NotFound):
            fs_storage.download("user", "f.txt")


class TestDownloadDir:
    async def test(self, file_factory, fs_storage: FileSystemStorage):
        # GIVEN
        await file_factory("user/a/x.txt", content=BytesIO(b"Hello"))
        await file_factory("user/a/y.txt", content=BytesIO(b"World"))
        await file_factory("user/a/c/f.txt", content=BytesIO(b"!"))
        await file_factory("user/b/z.txt")

        # WHEN
        chunks = fs_storage.downloaddir("user", "a")

        # THEN
        content = BytesIO(b"".join(chunk for chunk in chunks))

        with ZipFile(content, "r") as archive:
            assert set(archive.namelist()) == {"x.txt", "y.txt", "c/f.txt"}
            assert archive.read("x.txt") == b"Hello"
            assert archive.read("y.txt") == b"World"
            assert archive.read("c/f.txt") == b"!"

    async def test_on_empty_dir(self, file_factory, fs_storage: FileSystemStorage):
        await file_factory("user/empty_dir/", content=b"")
        chunks = fs_storage.downloaddir("user", "empty_dir")
        content = BytesIO(b"".join(chunk for chunk in chunks))
        with ZipFile(content, "r") as archive:
            assert archive.namelist() == []

    async def test_when_dir_does_not_exist(self, fs_storage: FileSystemStorage):
        chunks = fs_storage.downloaddir("user", "empty_dir")
        content = BytesIO(b"".join(chunk for chunk in chunks))
        with ZipFile(content, "r") as archive:
            assert archive.namelist() == []


async def test_exists(file_factory, fs_storage: FileSystemStorage):
    assert not await fs_storage.exists("user", "a")
    await file_factory("user/a/f.txt")
    assert await fs_storage.exists("user", "a")
    assert await fs_storage.exists("user", "a/f.txt")


async def test_iterdir(file_factory, fs_storage: FileSystemStorage):
    await file_factory("user/a/x.txt")
    await file_factory("user/a/y.txt")
    await file_factory("user/a/c/f.txt")
    await file_factory("user/b/z.txt")

    items = [item async for item in fs_storage.iterdir("user", "a")]
    c, x, y = sorted(
        items,
        key=operator.attrgetter("path")
    )

    assert c.name == "c"
    assert c.ns_path == "user"
    assert c.path == "a/c"
    assert c.is_dir()

    assert x.name == "x.txt"
    assert x.ns_path == "user"
    assert x.path == "a/x.txt"
    assert x.is_dir() is False

    assert y.name == "y.txt"
    assert y.ns_path == "user"
    assert y.path == "a/y.txt"
    assert y.is_dir() is False


async def test_iterdir_does_not_include_broken_symlinks(
    tmp_path: Path,
    file_factory,
    fs_storage: FileSystemStorage,
):
    await file_factory("user/x.txt")
    fullpath = await file_factory("user/y.txt")
    (tmp_path / "user/y_symlink.txt").symlink_to(fullpath)
    fullpath.unlink()

    files = [item async for item in fs_storage.iterdir("user", ".")]
    assert (len(files)) == 1
    assert files[0].path == "x.txt"


async def test_iterdir_but_path_does_not_exist(fs_storage: FileSystemStorage):
    with pytest.raises(File.NotFound):
        [item async for item in fs_storage.iterdir("user", "a")]


async def test_iterdir_but_it_is_a_file(file_factory, fs_storage: FileSystemStorage):
    await file_factory("user/f.txt")
    with pytest.raises(File.NotADirectory):
        [item async for item in fs_storage.iterdir("user", "f.txt")]


async def test_makedirs(fs_storage: FileSystemStorage):
    assert not await fs_storage.exists("user", "a")

    await fs_storage.makedirs("user", "a")
    assert await fs_storage.exists("user", "a")

    await fs_storage.makedirs("user", "a/b/c")
    assert await fs_storage.exists("user", "a/b/c")


async def test_makedirs_but_file_already_exists(
    file_factory, fs_storage: FileSystemStorage
):
    await file_factory("user/a")

    with pytest.raises(File.AlreadyExists):
        await fs_storage.makedirs("user", "a")


async def test_makedirs_but_parent_is_a_directory(
    file_factory, fs_storage: FileSystemStorage
):
    await file_factory("user/x.txt")

    with pytest.raises(File.NotADirectory):
        await fs_storage.makedirs("user", "x.txt/y.txt")


class TestMove:
    async def test(self, file_factory, fs_storage: FileSystemStorage):
        # GIVEN
        await file_factory("user/x.txt")
        # WHEN
        await fs_storage.move(at=("user", "x.txt"), to=("user", "y.txt"))
        # THEN
        assert not await fs_storage.exists("user", "x.txt")
        assert await fs_storage.exists("user", "y.txt")

    async def test_when_it_is_a_dir(self, file_factory, fs_storage: FileSystemStorage):
        await file_factory("user/a/x.txt")
        with pytest.raises(File.NotFound):
            await fs_storage.move(at=("user", "a"), to=("user", "b"))

    async def test_when_source_does_not_exist(self, fs_storage: FileSystemStorage):
        with pytest.raises(File.NotFound):
            await fs_storage.move(at=("user", "x.txt"), to=("user", "y.txt"))

    async def test_when_destination_does_not_exist(
        self, file_factory, fs_storage: FileSystemStorage
    ):
        # GIVEN
        await file_factory("user/x.txt")
        # WHEN
        await fs_storage.move(at=("user", "x.txt"), to=("user", "a/y.txt"))
        # THEN
        assert not await fs_storage.exists("user", "x.txt")
        assert await fs_storage.exists("user", "a/y.txt")

    async def test_when_destination_is_not_a_dir(
        self, file_factory, fs_storage: FileSystemStorage
    ):
        await file_factory("user/x.txt")
        await file_factory("user/y.txt")
        with pytest.raises(File.NotADirectory):
            await fs_storage.move(at=("user", "x.txt"), to=("user", "y.txt/x.txt"))


class TestMoveDir:
    async def test(self, file_factory, fs_storage: FileSystemStorage):
        # GIVEN
        await file_factory("user/a/f.txt")
        await file_factory("user/b/f.txt")
        # WHEN
        await fs_storage.movedir(at=("user", "a"), to=("user", "b/a"))
        # THEN
        assert not await fs_storage.exists("user", "a")
        assert not await fs_storage.exists("user", "a/f.txt")
        assert await fs_storage.exists("user", "b/a")
        assert await fs_storage.exists("user", "b/a/f.txt")

    async def test_when_it_is_a_file(self, file_factory, fs_storage: FileSystemStorage):
        # GIVEN
        await file_factory("user/a/f.txt")
        # WHEN
        await fs_storage.movedir(at=("user", "a/f.txt"), to=("user", "b/f.txt"))
        # THEN
        assert await fs_storage.exists("user", "a")
        assert await fs_storage.exists("user", "a/f.txt")
        assert not await fs_storage.exists("user", "b/f.txt")

    async def test_when_source_does_not_exist(self, fs_storage: FileSystemStorage):
        await fs_storage.movedir(at=("user", "a"), to=("user", "b"))

    async def test_when_destination_does_not_exist(
        self, file_factory, fs_storage: FileSystemStorage
    ):
        # GIVEN
        await file_factory("user/a/x.txt")
        # WHEN
        await fs_storage.movedir(at=("user", "a"), to=("user", "b/a"))
        # THEN
        assert not await fs_storage.exists("user", "a/x.txt")
        assert await fs_storage.exists("user", "b/a/x.txt")

    async def test_when_destination_is_not_a_dir(
        self, file_factory, fs_storage: FileSystemStorage
    ):
        await file_factory("user/a/f.txt")
        await file_factory("user/y.txt")
        with pytest.raises(File.NotADirectory):
            await fs_storage.movedir(at=("user", "a"), to=("user", "y.txt/a"))


async def test_save(fs_storage: FileSystemStorage):
    await fs_storage.makedirs("user", "a")
    content = BytesIO(b"I'm Dummy file!")
    file = await fs_storage.save("user", "a/f.txt", content=content)

    assert await fs_storage.exists("user", "a/f.txt")
    assert file.name == "f.txt"
    assert file.ns_path == "user"
    assert file.path == "a/f.txt"
    assert file.size == 15
    assert file.is_dir() is False


async def test_save_but_path_is_not_a_dir(file_factory, fs_storage: FileSystemStorage):
    await file_factory("user/f.txt")

    with pytest.raises(File.NotADirectory):
        await fs_storage.save("user", "f.txt/f.txt", content=BytesIO(b""))


async def test_save_overrides_existing_file(
    file_factory, fs_storage: FileSystemStorage
):
    fullpath = await file_factory("user/f.txt")
    assert fullpath.lstat().st_size == 15
    file = await fs_storage.save("user", "f.txt", content=BytesIO(b""))
    assert file.size == 0
