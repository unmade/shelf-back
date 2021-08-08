from __future__ import annotations

import operator
import shutil
from io import BytesIO
from typing import IO, TYPE_CHECKING

import pytest
from asgiref.sync import sync_to_async

from app import errors
from app.storage import LocalStorage, StorageFile

if TYPE_CHECKING:
    from pathlib import Path
    from app.typedefs import StrOrPath


@pytest.fixture()
def file_factory(tmp_path: Path):
    """
    Save file in a specified path with a given content and return full path.

    Any missing parents will be created.
    """
    @sync_to_async
    def create_file(
        path: StrOrPath,
        content: IO[bytes] = BytesIO(b"I'm Dummy File!"),
    ) -> Path:
        fullpath = tmp_path / path
        fullpath.parent.mkdir(exist_ok=True)
        with open(fullpath, 'wb') as buffer:
            shutil.copyfileobj(content, buffer)

        return fullpath

    return create_file


@pytest.fixture()
def storage_file() -> StorageFile:
    """A simple instance of a storage file."""
    return StorageFile(
        name="f.txt",
        path="f.txt",
        size=8,
        mtime=1628154987,
        is_dir=False,
    )


@pytest.fixture()
def local_storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path)


class TestStorageFile:
    def test_string_representation(self, storage_file: StorageFile):
        assert str(storage_file) == "f.txt"


@pytest.mark.asyncio
class TestLocalStorage:
    async def test_delete_file(self, file_factory, local_storage: LocalStorage):
        fullpath = await file_factory("f.txt")
        assert fullpath.exists()
        await local_storage.delete("f.txt")
        assert not fullpath.exists()

    async def test_delete_folder(self, file_factory, local_storage: LocalStorage):
        fullpath = await file_factory("a/f.txt")
        assert fullpath.exists()
        await local_storage.delete("a")
        assert not fullpath.exists()
        assert not fullpath.parent.exists()

    async def test_delete_but_file_does_not_exist(self, local_storage: LocalStorage):
        with pytest.raises(errors.FileNotFound):
            await local_storage.delete("f.txt")

    async def test_exists(self, file_factory, local_storage: LocalStorage):
        assert not await local_storage.exists("a")
        await file_factory("a/f.txt")
        assert await local_storage.exists("a")
        assert await local_storage.exists("a/f.txt")

    async def test_get_modified_time(self, file_factory, local_storage: LocalStorage):
        fullpath = await file_factory("a/f.txt")
        mtime = await local_storage.get_modified_time("a/f.txt")
        assert mtime == fullpath.lstat().st_mtime

        mtime = await local_storage.get_modified_time("a")
        assert mtime == fullpath.parent.lstat().st_mtime

    async def test_get_modified_time_but_file_does_not_exist(
        self, local_storage: LocalStorage
    ):
        with pytest.raises(errors.FileNotFound):
            await local_storage.get_modified_time("f.txt")

    async def test_iterdir(self, file_factory, local_storage: LocalStorage):
        await file_factory("a/x.txt")
        await file_factory("a/y.txt")
        await file_factory("b/z.txt")

        x, y = sorted(
            await local_storage.iterdir("a"),
            key=operator.attrgetter("path")
        )

        assert x.name == "x.txt"
        assert x.path == "a/x.txt"
        assert y.name == "y.txt"
        assert y.path == "a/y.txt"

    async def test_iterdir_but_path_does_not_exist(self, local_storage: LocalStorage):
        with pytest.raises(errors.FileNotFound):
            await local_storage.iterdir("a")

    async def test_iterdir_but_it_is_a_file(
        self, file_factory, local_storage: LocalStorage
    ):
        await file_factory("f.txt")
        with pytest.raises(errors.NotADirectory):
            await local_storage.iterdir("f.txt")

    async def test_makedirs(self, local_storage: LocalStorage):
        assert not await local_storage.exists("a")

        await local_storage.makedirs("a")
        assert await local_storage.exists("a")

        await local_storage.makedirs("a/b/c")
        assert await local_storage.exists("a/b/c")

    async def test_makedirs_but_file_already_exists(
        self, file_factory, local_storage: LocalStorage
    ):
        await file_factory("a")

        with pytest.raises(errors.FileAlreadyExists):
            await local_storage.makedirs("a")

    async def test_makedirs_but_parent_is_a_directory(
        self, file_factory, local_storage: LocalStorage
    ):
        await file_factory("x.txt")

        with pytest.raises(errors.NotADirectory):
            await local_storage.makedirs("x.txt/y.txt")

    async def test_move_file(self, file_factory, local_storage: LocalStorage):
        await file_factory("x.txt")

        await local_storage.move("x.txt", "y.txt")

        assert not await local_storage.exists("x.txt")
        assert await local_storage.exists("y.txt")

    async def test_move_folder(self, file_factory, local_storage: LocalStorage):
        await file_factory("a/f.txt")
        await file_factory("b/f.txt")

        # move folder 'a' to 'a/b' under name 'a'
        await local_storage.move("a", "b/a")

        assert not await local_storage.exists("a")
        assert await local_storage.exists("b/a")
        assert await local_storage.exists("b/a/f.txt")

    async def test_move_but_source_does_not_exist(self, local_storage: LocalStorage):
        with pytest.raises(errors.FileNotFound):
            await local_storage.move("x.txt", "y.txt")

    async def test_move_but_destination_does_not_exist(
        self, file_factory, local_storage: LocalStorage
    ):
        await file_factory("x.txt")
        with pytest.raises(errors.FileNotFound):
            await local_storage.move("x.txt", "a/y.txt")

    async def test_move_but_destination_is_not_a_directory(
        self, file_factory, local_storage: LocalStorage
    ):
        await file_factory("x.txt")
        await file_factory("y.txt")
        with pytest.raises(errors.NotADirectory):
            await local_storage.move("x.txt", "y.txt/x.txt")

    async def test_save(self, local_storage: LocalStorage):
        await local_storage.makedirs("a")
        file = await local_storage.save("a/f.txt", content=BytesIO(b"I'm Dummy file!"))

        await local_storage.exists("a/f.txt")
        assert file.name == "f.txt"
        assert file.path == "a/f.txt"
        assert file.size == 15
        assert file.is_dir is False

    async def test_save_but_path_is_not_a_folder(
        self, file_factory, local_storage: LocalStorage
    ):
        await file_factory("f.txt")

        with pytest.raises(errors.NotADirectory):
            await local_storage.save("f.txt/f.txt", content=BytesIO(b""))

    async def test_save_overrides_existing_file(
        self, file_factory, local_storage: LocalStorage
    ):
        fullpath = await file_factory("f.txt")
        assert fullpath.lstat().st_size == 15
        file = await local_storage.save("f.txt", content=BytesIO(b""))
        assert file.size == 0

    async def test_size(self, file_factory, local_storage: LocalStorage):
        fullpath = await file_factory("f.txt")
        size = await local_storage.size("f.txt")
        assert size == fullpath.lstat().st_size

    async def test_size_but_file_does_not_exist(self, local_storage: LocalStorage):
        with pytest.raises(errors.FileNotFound):
            await local_storage.size("f.txt")

    async def test_thumbnail(
        self, file_factory, image_content, local_storage: LocalStorage
    ):
        await file_factory("im.jpg", content=image_content)
        size, content = await local_storage.thumbnail("im.jpg", size=128)
        assert size == 883
        assert size == len(content.read())

    async def test_thumbnail_but_path_is_a_directory(
        self, file_factory, image_content, local_storage: LocalStorage
    ):
        await file_factory("a/im.jpg", content=image_content)

        with pytest.raises(errors.IsADirectory) as excinfo:
            await local_storage.thumbnail("a", size=128)

        assert str(excinfo.value) == "Path 'a' is a directory"

    async def test_thumbnail_but_file_is_not_an_image(
        self, file_factory, local_storage: LocalStorage
    ):
        await file_factory("im.jpg")

        with pytest.raises(errors.ThumbnailUnavailable) as excinfo:
            await local_storage.thumbnail("im.jpg", size=128)

        assert str(excinfo.value) == "Can't generate thumbnail for a file: 'im.jpg'"

    async def test_thumbnail_but_path_does_not_exist(
        self, local_storage: LocalStorage
    ):
        with pytest.raises(errors.FileNotFound):
            await local_storage.thumbnail("im.jpg", size=128)
