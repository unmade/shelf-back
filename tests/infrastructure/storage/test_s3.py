from __future__ import annotations

import operator
from io import BytesIO
from typing import TYPE_CHECKING, Protocol
from zipfile import ZipFile

import pytest

from app.app.files.domain.file import File
from app.infrastructure.storage.s3.clients.exceptions import AccessDenied

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath, IFileContent
    from app.infrastructure.storage import S3Storage
    from app.infrastructure.storage.s3.clients import AsyncS3Client

    class FileFactory(Protocol):
        async def __call__(
            self, path: AnyPath, content: bytes | BytesIO = b"I'm Dummy File!"
        ):
            ...

pytestmark = [pytest.mark.asyncio, pytest.mark.storage_s3]


@pytest.fixture
def file_factory(s3_bucket: str, s3_client: AsyncS3Client) -> FileFactory:
    """
    A file factory for a S3Storage.

    Save file in a specified path with a given content and return full path.
    Any missing parents will be created.
    """
    async def create_file(
        path: AnyPath,
        content: bytes | BytesIO = b"I'm Dummy File!",
    ) -> None:
        from tests.fixtures.app.files import FileContent

        if isinstance(content, bytes):
            _content = FileContent(content)
        else:
            _content = FileContent.from_buffer(content)

        await s3_client.upload_obj(s3_bucket, str(path), _content)

    return create_file


class TestDelete:
    async def test(self, s3_storage: S3Storage, file_factory: FileFactory):
        await file_factory("user/f.txt")
        assert await s3_storage.exists("user", "f.txt")
        await s3_storage.delete("user", "f.txt")
        assert not await s3_storage.exists("user", "f.txt")

    async def test_when_it_is_a_dir(
        self, s3_storage: S3Storage, file_factory: FileFactory
    ):
        await file_factory("user/a/f.txt")
        await s3_storage.delete("user", "a")
        assert await s3_storage.exists("user", "a/f.txt")

    async def test_when_file_does_not_exist(self, s3_storage: S3Storage):
        await s3_storage.delete("user", "f.txt")


class TestDeletedir:
    async def test_deletedir(self, s3_storage: S3Storage, file_factory: FileFactory):
        await file_factory("user/a/f.txt")
        await s3_storage.deletedir("user", "a")
        assert not await s3_storage.exists("user", "a")
        assert not await s3_storage.exists("user", "a/f.txt")

    async def test_deletedir_but_it_is_a_file(
        self, s3_storage: S3Storage, file_factory: FileFactory
    ):
        await file_factory("user/f.txt")
        await s3_storage.deletedir("user", "f.txt")
        assert await s3_storage.exists("user", "f.txt")

    async def test_deletedir_but_dir_does_not_exist(self, s3_storage: S3Storage):
        await s3_storage.deletedir("user", "a")


class TestEmptydir:
    async def test_emptydir(self, s3_storage: S3Storage, file_factory: FileFactory):
        await file_factory("user/a/f.txt")
        await file_factory("user/a/b/f.txt")
        await s3_storage.emptydir("user", "a")
        assert not await s3_storage.exists("user", "a/f.txt")
        assert not await s3_storage.exists("user", "a/b/f.txt")

    async def test_emptydir_but_it_is_a_file(
        self, s3_storage: S3Storage, file_factory: FileFactory
    ):
        await file_factory("user/f.txt")
        await s3_storage.emptydir("user", "f.txt")
        assert await s3_storage.exists("user", "f.txt")

    async def test_emptydir_but_dir_does_not_exist(self, s3_storage: S3Storage):
        await s3_storage.emptydir("user", "a")


class TestDownload:
    async def test(self, s3_storage: S3Storage, file_factory: FileFactory):
        # GIVEN
        await file_factory("user/f.txt")
        # WHEN
        chunks = s3_storage.download("user", "f.txt")
        # THEN
        content = BytesIO(b"".join([chunk async for chunk in chunks]))
        assert content.read() == b"I'm Dummy File!"

    async def test_when_it_is_a_dir(
        self, s3_storage: S3Storage, file_factory: FileFactory
    ):
        await file_factory("user/a/f.txt")
        with pytest.raises(File.NotFound):
            await anext(s3_storage.download("user", "a"))

    async def test_when_file_does_not_exist(self, s3_storage: S3Storage):
        with pytest.raises(File.NotFound):
            await anext(s3_storage.download("user", "f.txt"))


class TestDownloadDir:
    async def test(self, s3_storage: S3Storage, file_factory: FileFactory):
        # GIVEN
        await file_factory("user/a/x.txt", content=BytesIO(b"Hello"))
        await file_factory("user/a/y.txt", content=BytesIO(b"World"))
        await file_factory("user/a/c/f.txt", content=BytesIO(b"!"))
        await file_factory("user/b/z.txt")

        # WHEN
        chunks = s3_storage.downloaddir("user", "a")

        # THEN
        content = BytesIO(b"".join(chunk for chunk in chunks))
        with ZipFile(content, "r") as archive:
            assert set(archive.namelist()) == {"x.txt", "y.txt", "c/f.txt"}
            assert archive.read("x.txt") == b"Hello"
            assert archive.read("y.txt") == b"World"
            assert archive.read("c/f.txt") == b"!"

    async def test_on_empty_dir(self, s3_storage: S3Storage, file_factory: FileFactory):
        # GIVEN
        await file_factory("user/empty_dir/", content=b"")
        # WHEN
        chunks = s3_storage.downloaddir("user", "empty_dir")
        # THEN
        content = BytesIO(b"".join(chunk for chunk in chunks))
        with ZipFile(content, "r") as archive:
            assert archive.namelist() == ["."]

    async def test_when_dir_does_not_exist(self, s3_storage: S3Storage):
        chunks = s3_storage.downloaddir("user", "empty_dir")
        content = BytesIO(b"".join(chunk for chunk in chunks))
        with ZipFile(content, "r") as archive:
            assert archive.namelist() == []


class TestIterdir:
    async def test(self, s3_storage: S3Storage, file_factory: FileFactory):
        await file_factory("user/a/x.txt")
        await file_factory("user/a/y.txt")
        await file_factory("user/a/c/f.txt")
        await file_factory("user/b/z.txt")

        items = [item async for item in s3_storage.iterdir("user", "a")]
        c, x, y = sorted(
            items,
            key=operator.attrgetter("path")
        )

        assert c.name == "c"
        assert c.ns_path == "user"
        assert c.path == "a/c"
        assert c.mtime == 0
        assert c.size == 0
        assert c.is_dir()

        assert x.name == "x.txt"
        assert x.ns_path == "user"
        assert x.path == "a/x.txt"
        assert x.mtime > 0
        assert x.size == 15
        assert x.is_dir() is False

        assert y.name == "y.txt"
        assert y.ns_path == "user"
        assert y.path == "a/y.txt"
        assert y.mtime > 0
        assert y.size == 15
        assert y.is_dir() is False

    async def test_on_empty_dir(self, s3_storage: S3Storage, file_factory: FileFactory):
        await file_factory("user/empty_dir/", content=b"")
        result = [item async for item in s3_storage.iterdir("user", "emptydir")]
        assert result == []

    async def test_when_path_does_not_exist(self, s3_storage: S3Storage):
        result = [item async for item in s3_storage.iterdir("user", "a")]
        assert len(result) == 0

    async def test_when_it_is_a_file(
        self, s3_storage: S3Storage, file_factory: FileFactory
    ):
        await file_factory("user/f.txt")
        result = [item async for item in s3_storage.iterdir("user", "f.txt")]
        assert len(result) == 0


class TestMakedir:
    async def test(self, s3_storage: S3Storage):
        await s3_storage.makedirs("admin", "a/b/c")


class TestMove:
    async def test(self, s3_storage: S3Storage, file_factory: FileFactory):
        # GIVEN
        await file_factory("user/x.txt")
        # WHEN
        await s3_storage.move(at=("user", "x.txt"), to=("user", "y.txt"))
        # THEN
        assert not await s3_storage.exists("user", "x.txt")
        assert await s3_storage.exists("user", "y.txt")

    async def test_when_it_is_a_dir(
        self, s3_storage: S3Storage, file_factory: FileFactory
    ):
        await file_factory("user/a/x.txt")
        with pytest.raises(File.NotFound):
            await s3_storage.move(at=("user", "a"), to=("user", "b"))

    async def test_when_source_does_not_exist(self, s3_storage: S3Storage):
        with pytest.raises(File.NotFound):
            await s3_storage.move(at=("user", "x.txt"), to=("user", "y.txt"))

    async def test_when_destination_does_not_exist(
        self, s3_storage: S3Storage, file_factory: FileFactory
    ):
        # GIVEN
        await file_factory("user/x.txt")
        # WHEN
        await s3_storage.move(at=("user", "x.txt"), to=("user", "a/y.txt"))
        # THEN
        assert not await s3_storage.exists("user", "x.txt")
        assert await s3_storage.exists("user", "a/y.txt")

    async def test_when_destination_is_not_a_dir(
        self, s3_storage: S3Storage, file_factory: FileFactory
    ):
        await file_factory("user/x.txt")
        await file_factory("user/y.txt")

        with pytest.raises(AccessDenied):
            await s3_storage.move(at=("user", "x.txt"), to=("user", "y.txt/x.txt"))


class TestMoveDir:
    async def test(self, s3_storage: S3Storage, file_factory: FileFactory):
        # GIVEN
        await file_factory("user/a/f.txt")
        await file_factory("user/b/f.txt")
        # WHEN
        await s3_storage.movedir(at=("user", "a"), to=("user", "b/a"))
        # THEN
        assert not await s3_storage.exists("user", "a/f.txt")
        assert await s3_storage.exists("user", "b/a/f.txt")

    async def test_on_empty_dir(self, s3_storage: S3Storage, file_factory: FileFactory):
        # GIVEN
        await file_factory("user/empty_dir/", content=b"")
        # WHEN
        await s3_storage.movedir(at=("user", "empty_dir"), to=("user", "a"))
        # THEN
        assert not await s3_storage.exists("user", "empty_dir")
        assert await s3_storage.exists("user", "a")

    async def test_when_it_is_a_file(
        self, s3_storage: S3Storage, file_factory: FileFactory
    ):
        # GIVEN
        await file_factory("user/a/f.txt")
        # WHEN
        await s3_storage.movedir(at=("user", "a/f.txt"), to=("user", "b/f.txt"))
        # THEN
        assert await s3_storage.exists("user", "a/f.txt")
        assert not await s3_storage.exists("user", "b/f.txt")

    async def test_when_source_does_not_exist(self, s3_storage: S3Storage):
        await s3_storage.movedir(at=("user", "a"), to=("user", "b"))

    async def test_when_destination_does_not_exist(
        self, s3_storage: S3Storage, file_factory: FileFactory
    ):
        # GIVEN
        await file_factory("user/a/x.txt")
        # WHEN
        await s3_storage.movedir(at=("user", "a"), to=("user", "b/a"))
        # THEN
        assert not await s3_storage.exists("user", "a/x.txt")
        assert await s3_storage.exists("user", "b/a/x.txt")

    async def test_when_destination_is_not_a_dir(
        self, s3_storage: S3Storage, file_factory: FileFactory
    ):
        await file_factory("user/a/f.txt")
        await file_factory("user/y.txt")

        with pytest.raises(ExceptionGroup) as excinfo:
            await s3_storage.movedir(at=("user", "a"), to=("user", "y.txt/a"))

        eg = excinfo.value
        match, rest = eg.split(AccessDenied)
        assert match is not None
        assert rest is None


class TestSave:
    async def test(
        self,
        s3_storage: S3Storage,
        s3_bucket: str,
        s3_client: AsyncS3Client,
        content: IFileContent,
    ):
        file = await s3_storage.save("user", "a/f.txt", content=content)

        obj = await s3_client.head_object(s3_bucket, "user/a/f.txt")
        assert file.name == "f.txt"
        assert file.ns_path == "user"
        assert file.path == "a/f.txt"
        assert file.size == obj.size == content.size
        assert file.is_dir() is False

    async def test_when_path_is_not_a_dir(
        self, s3_storage: S3Storage, file_factory: FileFactory, content: IFileContent
    ):
        await file_factory("user/f.txt")
        with pytest.raises(AccessDenied):
            await s3_storage.save("user", "f.txt/f.txt", content=content)

    async def test_when_overrides_existing_file(
        self, s3_storage: S3Storage, file_factory: FileFactory, content: IFileContent
    ):
        await file_factory("user/f.txt")
        file = await s3_storage.save("user", "f.txt", content=content)
        assert file.size == content.size
