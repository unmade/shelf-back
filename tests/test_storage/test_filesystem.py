from __future__ import annotations

import operator
import shutil
from io import BytesIO
from typing import IO, TYPE_CHECKING
from zipfile import ZipFile

import pytest
from asgiref.sync import sync_to_async

from app import errors
from app.storage.filesystem import FileSystemStorage

if TYPE_CHECKING:
    from pathlib import Path

    from app.typedefs import StrOrPath

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
        path: StrOrPath,
        content: IO[bytes] = BytesIO(b"I'm Dummy File!"),
    ) -> Path:
        fullpath = tmp_path / path
        fullpath.parent.mkdir(parents=True, exist_ok=True)
        with open(fullpath, 'wb') as buffer:
            shutil.copyfileobj(content, buffer)

        return fullpath

    return create_file


@pytest.fixture
def fs_storage(tmp_path: Path) -> FileSystemStorage:
    """An instance of FileSystemStorage with `tmp_path` fixture as a location."""
    return FileSystemStorage(tmp_path)


async def test_delete_file(file_factory, fs_storage: FileSystemStorage):
    fullpath = await file_factory("user/f.txt")
    assert fullpath.exists()
    await fs_storage.delete("user", "f.txt")
    assert not fullpath.exists()


async def test_delete_folder(file_factory, fs_storage: FileSystemStorage):
    fullpath = await file_factory("user/a/f.txt")
    assert fullpath.exists()
    await fs_storage.delete("user", "a")
    assert not fullpath.exists()
    assert not fullpath.parent.exists()


async def test_delete_but_file_does_not_exist(fs_storage: FileSystemStorage):
    with pytest.raises(errors.FileNotFound):
        await fs_storage.delete("user", "f.txt")


async def test_download_file(file_factory, fs_storage: FileSystemStorage):
    await file_factory("user/f.txt")
    buffer = BytesIO()
    for chunk in fs_storage.download("user", "f.txt"):
        buffer.write(chunk)
    buffer.seek(0)
    assert buffer.read() == b"I'm Dummy File!"


async def test_download_folder(file_factory, fs_storage: FileSystemStorage):
    await file_factory("user/a/x.txt", content=BytesIO(b"Hello"))
    await file_factory("user/a/y.txt", content=BytesIO(b"World"))

    await file_factory("user/a/b/z.txt", content=BytesIO(b"!"))
    buffer = BytesIO()
    for chunk in fs_storage.download("user", "a"):
        buffer.write(chunk)
    buffer.seek(0)

    with ZipFile(buffer, "r") as archive:
        assert sorted(archive.namelist()) == sorted(["x.txt", "y.txt", "b/z.txt"])
        assert archive.read("x.txt") == b"Hello"
        assert archive.read("y.txt") == b"World"
        assert archive.read("b/z.txt") == b"!"


async def test_exists(file_factory, fs_storage: FileSystemStorage):
    assert not await fs_storage.exists("user", "a")
    await file_factory("user/a/f.txt")
    assert await fs_storage.exists("user", "a")
    assert await fs_storage.exists("user", "a/f.txt")


async def test_get_modified_time(file_factory, fs_storage: FileSystemStorage):
    fullpath = await file_factory("user/a/f.txt")
    mtime = await fs_storage.get_modified_time("user", "a/f.txt")
    assert mtime == fullpath.lstat().st_mtime

    mtime = await fs_storage.get_modified_time("user", "a")
    assert mtime == fullpath.parent.lstat().st_mtime


async def test_get_modified_time_but_file_does_not_exist(fs_storage: FileSystemStorage):
    with pytest.raises(errors.FileNotFound):
        await fs_storage.get_modified_time("user", "f.txt")


async def test_iterdir(file_factory, fs_storage: FileSystemStorage):
    await file_factory("user/a/x.txt")
    await file_factory("user/a/y.txt")
    await file_factory("user/b/z.txt")

    x, y = sorted(
        await fs_storage.iterdir("user", "a"),
        key=operator.attrgetter("path")
    )

    assert x.name == "x.txt"
    assert x.ns_path == "user"
    assert x.path == "a/x.txt"
    assert y.name == "y.txt"
    assert y.ns_path == "user"
    assert y.path == "a/y.txt"


async def test_iterdir_does_not_include_broken_symlinks(
    tmp_path: Path,
    file_factory,
    fs_storage: FileSystemStorage,
):
    await file_factory("user/x.txt")
    fullpath = await file_factory("user/y.txt")
    (tmp_path / "user/y_symlink.txt").symlink_to(fullpath)
    fullpath.unlink()

    files = list(await fs_storage.iterdir("user", "."))
    assert(len(files)) == 1
    assert files[0].path == "x.txt"


async def test_iterdir_but_path_does_not_exist(fs_storage: FileSystemStorage):
    with pytest.raises(errors.FileNotFound):
        list(await fs_storage.iterdir("user", "a"))


async def test_iterdir_but_it_is_a_file(file_factory, fs_storage: FileSystemStorage):
    await file_factory("user/f.txt")
    with pytest.raises(errors.NotADirectory):
        list(await fs_storage.iterdir("user", "f.txt"))


async def test_makedirs(tmp_path: Path, fs_storage: FileSystemStorage):
    assert not (tmp_path / "user/a").exists()

    await fs_storage.makedirs("user", "a")
    assert (tmp_path / "user/a").exists()

    await fs_storage.makedirs("user", "a/b/c")
    assert (tmp_path / "user/a/b/c").exists()


async def test_makedirs_but_file_already_exists(
    file_factory, fs_storage: FileSystemStorage
):
    await file_factory("user/a")

    with pytest.raises(errors.FileAlreadyExists):
        await fs_storage.makedirs("user", "a")


async def test_makedirs_but_parent_is_a_directory(
    file_factory, fs_storage: FileSystemStorage
):
    await file_factory("user/x.txt")

    with pytest.raises(errors.NotADirectory):
        await fs_storage.makedirs("user", "x.txt/y.txt")


async def test_move_file(tmp_path: Path, file_factory, fs_storage: FileSystemStorage):
    await file_factory("user/x.txt")

    await fs_storage.move("user", "x.txt", "y.txt")

    assert not (tmp_path / "user/x.txt").exists()
    assert (tmp_path / "user/y.txt").exists


async def test_move_folder(tmp_path: Path, file_factory, fs_storage: FileSystemStorage):
    await file_factory("user/a/f.txt")
    await file_factory("user/b/f.txt")

    # move folder 'a' to 'a/b' under name 'a'
    await fs_storage.move("user", "a", "b/a")

    assert not (tmp_path / "user/a").exists()
    assert (tmp_path / "user/b/a/f.txt").exists()


async def test_move_but_source_does_not_exist(fs_storage: FileSystemStorage):
    with pytest.raises(errors.FileNotFound):
        await fs_storage.move("user", "x.txt", "y.txt")


async def test_move_but_destination_does_not_exist(
    file_factory, fs_storage: FileSystemStorage
):
    await file_factory("user/x.txt")
    with pytest.raises(errors.FileNotFound):
        await fs_storage.move("user", "x.txt", "a/y.txt")


async def test_move_but_destination_is_not_a_directory(
    file_factory, fs_storage: FileSystemStorage
):
    await file_factory("user/x.txt")
    await file_factory("user/y.txt")
    with pytest.raises(errors.NotADirectory):
        await fs_storage.move("user", "x.txt", "y.txt/x.txt")


async def test_save(tmp_path: Path, fs_storage: FileSystemStorage):
    await fs_storage.makedirs("user", "a")
    content = BytesIO(b"I'm Dummy file!")
    file = await fs_storage.save("user", "a/f.txt", content=content)

    assert (tmp_path / "user/a/f.txt").exists()
    assert file.name == "f.txt"
    assert file.ns_path == "user"
    assert file.path == "a/f.txt"
    assert file.size == 15
    assert file.is_dir() is False


async def test_save_but_path_is_not_a_folder(
    file_factory, fs_storage: FileSystemStorage
):
    await file_factory("user/f.txt")

    with pytest.raises(errors.NotADirectory):
        await fs_storage.save("user", "f.txt/f.txt", content=BytesIO(b""))


async def test_save_overrides_existing_file(
    file_factory, fs_storage: FileSystemStorage
):
    fullpath = await file_factory("user/f.txt")
    assert fullpath.lstat().st_size == 15
    file = await fs_storage.save("user", "f.txt", content=BytesIO(b""))
    assert file.size == 0


async def test_size(file_factory, fs_storage: FileSystemStorage):
    fullpath = await file_factory("user/f.txt")
    size = await fs_storage.size("user", "f.txt")
    assert size == fullpath.lstat().st_size


async def test_size_but_file_does_not_exist(fs_storage: FileSystemStorage):
    with pytest.raises(errors.FileNotFound):
        await fs_storage.size("user", "f.txt")


async def test_thumbnail(
    file_factory, image_content, fs_storage: FileSystemStorage
):
    await file_factory("user/im.jpg", content=image_content)
    size, content = await fs_storage.thumbnail("user", "im.jpg", size=128)
    assert size == 883
    assert size == len(content.read())


async def test_thumbnail_but_path_is_a_directory(
    file_factory, image_content, fs_storage: FileSystemStorage
):
    await file_factory("user/a/im.jpg", content=image_content)

    with pytest.raises(errors.IsADirectory) as excinfo:
        await fs_storage.thumbnail("user", "a", size=128)

    assert str(excinfo.value) == "Path 'a' is a directory"


async def test_thumbnail_but_file_is_not_an_image(
    file_factory, fs_storage: FileSystemStorage
):
    await file_factory("user/im.jpg")

    with pytest.raises(errors.ThumbnailUnavailable) as excinfo:
        await fs_storage.thumbnail("user", "im.jpg", size=128)

    assert str(excinfo.value) == "Can't generate thumbnail for a file: 'im.jpg'"


async def test_thumbnail_but_path_does_not_exist(fs_storage: FileSystemStorage):
    with pytest.raises(errors.FileNotFound):
        await fs_storage.thumbnail("user", "im.jpg", size=128)
