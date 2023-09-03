from __future__ import annotations

import operator
from io import BytesIO
from typing import TYPE_CHECKING
from zipfile import ZipFile

import pytest
from asgiref.sync import sync_to_async

from app.app.files.domain.file import File

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath
    from app.infrastructure.storage.async_s3.storage import AsyncS3Storage

pytestmark = [pytest.mark.asyncio, pytest.mark.storage_s3]


@pytest.fixture
def file_factory(s3_bucket: str, s3_resource):
    """
    A file factory for a S3Storage.

    Save file in a specified path with a given content and return full path.
    Any missing parents will be created.
    """
    @sync_to_async
    def create_file(
        path: AnyPath,
        content: bytes | BytesIO = b"I'm Dummy File!",
    ) -> None:
        if isinstance(content, bytes):
            content = BytesIO(content)

        s3_resource.Bucket(s3_bucket).upload_fileobj(content, path)

    return create_file


class TestDelete:
    async def test(self, file_factory, async_s3_storage: AsyncS3Storage):
        await file_factory("user/f.txt")
        assert await async_s3_storage.exists("user", "f.txt")
        await async_s3_storage.delete("user", "f.txt")
        assert not await async_s3_storage.exists("user", "f.txt")

    async def test_when_it_is_a_dir(
        self, file_factory, async_s3_storage: AsyncS3Storage
    ):
        await file_factory("user/a/f.txt")
        await async_s3_storage.delete("user", "a")
        # assert await async_s3_storage.exists("user", "a")
        assert await async_s3_storage.exists("user", "a/f.txt")

    async def test_when_file_does_not_exist(self, async_s3_storage: AsyncS3Storage):
        await async_s3_storage.delete("user", "f.txt")


class TestDeletedir:
    async def test_deletedir(self, file_factory, async_s3_storage: AsyncS3Storage):
        await file_factory("user/a/f.txt")
        await async_s3_storage.deletedir("user", "a")
        assert not await async_s3_storage.exists("user", "a")
        assert not await async_s3_storage.exists("user", "a/f.txt")

    async def test_deletedir_but_it_is_a_file(
        self, file_factory, async_s3_storage: AsyncS3Storage
    ):
        await file_factory("user/f.txt")
        await async_s3_storage.deletedir("user", "f.txt")
        assert await async_s3_storage.exists("user", "f.txt")

    async def test_deletedir_but_dir_does_not_exist(
        self, async_s3_storage: AsyncS3Storage
    ):
        await async_s3_storage.deletedir("user", "a")


class TestEmptydir:
    async def test_emptydir(self, file_factory, async_s3_storage: AsyncS3Storage):
        await file_factory("user/a/f.txt")
        await file_factory("user/a/b/f.txt")
        await async_s3_storage.emptydir("user", "a")
        # assert not await async_s3_storage.exists("user", "a")
        assert not await async_s3_storage.exists("user", "a/f.txt")
        # assert not await async_s3_storage.exists("user", "a/b")
        assert not await async_s3_storage.exists("user", "a/b/f.txt")

    async def test_emptydir_but_it_is_a_file(
        self, file_factory, async_s3_storage: AsyncS3Storage
    ):
        await file_factory("user/f.txt")
        await async_s3_storage.emptydir("user", "f.txt")
        assert await async_s3_storage.exists("user", "f.txt")

    async def test_emptydir_but_dir_does_not_exist(
        self, async_s3_storage: AsyncS3Storage
    ):
        await async_s3_storage.emptydir("user", "a")


class TestDownload:
    async def test(self, file_factory, async_s3_storage: AsyncS3Storage):
        # GIVEN
        await file_factory("user/f.txt")
        # WHEN
        chunks = async_s3_storage.download("user", "f.txt")
        # THEN
        content = BytesIO(b"".join([chunk async for chunk in chunks]))
        assert content.read() == b"I'm Dummy File!"

    @pytest.mark.skip("figure out how to handle errors in the async iterator")
    async def test_when_it_is_a_dir(
        self, file_factory, async_s3_storage: AsyncS3Storage
    ):
        await file_factory("user/a/f.txt")
        with pytest.raises(File.NotFound):
            async_s3_storage.download("user", "a")

    @pytest.mark.skip("figure out how to handle errors in the async iterator")
    async def test_when_file_does_not_exist(self, async_s3_storage: AsyncS3Storage):
        with pytest.raises(File.NotFound):
            async_s3_storage.download("user", "f.txt")


class TestDownloadDir:
    async def test(self, file_factory, async_s3_storage: AsyncS3Storage):
        # GIVEN
        await file_factory("user/a/x.txt", content=BytesIO(b"Hello"))
        await file_factory("user/a/y.txt", content=BytesIO(b"World"))
        await file_factory("user/a/c/f.txt", content=BytesIO(b"!"))
        await file_factory("user/b/z.txt")

        # WHEN
        chunks = async_s3_storage.downloaddir("user", "a")

        # THEN
        content = BytesIO(b"".join(chunk for chunk in chunks))
        with ZipFile(content, "r") as archive:
            assert set(archive.namelist()) == {"x.txt", "y.txt", "c/f.txt"}
            assert archive.read("x.txt") == b"Hello"
            assert archive.read("y.txt") == b"World"
            assert archive.read("c/f.txt") == b"!"

    async def test_on_empty_dir(self, file_factory, async_s3_storage: AsyncS3Storage):
        # GIVEN
        await file_factory("user/empty_dir/", content=b"")
        # WHEN
        chunks = async_s3_storage.downloaddir("user", "empty_dir")
        # THEN
        content = BytesIO(b"".join(chunk for chunk in chunks))
        with ZipFile(content, "r") as archive:
            assert archive.namelist() == ["."]

    async def test_when_dir_does_not_exist(self, async_s3_storage: AsyncS3Storage):
        chunks = async_s3_storage.downloaddir("user", "empty_dir")
        content = BytesIO(b"".join(chunk for chunk in chunks))
        with ZipFile(content, "r") as archive:
            assert archive.namelist() == []


class TestIterdir:
    async def test(self, file_factory, async_s3_storage: AsyncS3Storage):
        await file_factory("user/a/x.txt")
        await file_factory("user/a/y.txt")
        await file_factory("user/a/c/f.txt")
        await file_factory("user/b/z.txt")

        items = [item async for item in async_s3_storage.iterdir("user", "a")]
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

    async def test_on_empty_dir(self, file_factory, async_s3_storage: AsyncS3Storage):
        await file_factory("user/empty_dir/", content=b"")
        result = [item async for item in async_s3_storage.iterdir("user", "emptydir")]
        assert result == []

    async def test_when_path_does_not_exist(self, async_s3_storage: AsyncS3Storage):
        result = [item async for item in async_s3_storage.iterdir("user", "a")]
        assert len(result) == 0

    async def test_when_it_is_a_file(
        self, file_factory, async_s3_storage: AsyncS3Storage
    ):
        await file_factory("user/f.txt")
        result = [item async for item in async_s3_storage.iterdir("user", "f.txt")]
        assert len(result) == 0


class TestMove:
    async def test(self, file_factory, async_s3_storage: AsyncS3Storage):
        # GIVEN
        await file_factory("user/x.txt")
        # WHEN
        await async_s3_storage.move(at=("user", "x.txt"), to=("user", "y.txt"))
        # THEN
        assert not await async_s3_storage.exists("user", "x.txt")
        assert await async_s3_storage.exists("user", "y.txt")

    async def test_when_it_is_a_dir(
        self, file_factory, async_s3_storage: AsyncS3Storage
    ):
        await file_factory("user/a/x.txt")
        with pytest.raises(File.NotFound):
            await async_s3_storage.move(at=("user", "a"), to=("user", "b"))

    async def test_when_source_does_not_exist(self, async_s3_storage: AsyncS3Storage):
        with pytest.raises(File.NotFound):
            await async_s3_storage.move(at=("user", "x.txt"), to=("user", "y.txt"))

    async def test_when_destination_does_not_exist(
        self, file_factory, async_s3_storage: AsyncS3Storage
    ):
        # GIVEN
        await file_factory("user/x.txt")
        # WHEN
        await async_s3_storage.move(at=("user", "x.txt"), to=("user", "a/y.txt"))
        # THEN
        assert not await async_s3_storage.exists("user", "x.txt")
        assert await async_s3_storage.exists("user", "a/y.txt")

    @pytest.mark.skip("that move should be prohibitted")
    async def test_when_destination_is_not_a_dir(
        self, file_factory, async_s3_storage: AsyncS3Storage
    ):
        await file_factory("user/x.txt")
        await file_factory("user/y.txt")

        await async_s3_storage.move(at=("user", "x.txt"), to=("user", "y.txt/x.txt"))
        assert await async_s3_storage.exists("user", "y.txt")
        assert await async_s3_storage.exists("user", "y.txt/x.txt")


class TestMoveDir:
    async def test(self, file_factory, async_s3_storage: AsyncS3Storage):
        # GIVEN
        await file_factory("user/a/f.txt")
        await file_factory("user/b/f.txt")
        # WHEN
        await async_s3_storage.movedir(at=("user", "a"), to=("user", "b/a"))
        # THEN
        assert not await async_s3_storage.exists("user", "a/f.txt")
        assert await async_s3_storage.exists("user", "b/a/f.txt")

    async def test_on_empty_dir(self, file_factory, async_s3_storage: AsyncS3Storage):
        # GIVEN
        await file_factory("user/empty_dir/", content=b"")
        # WHEN
        await async_s3_storage.movedir(at=("user", "empty_dir"), to=("user", "a"))
        # THEN
        assert not await async_s3_storage.exists("user", "empty_dir")
        assert await async_s3_storage.exists("user", "a")

    async def test_when_it_is_a_file(
        self, file_factory, async_s3_storage: AsyncS3Storage
    ):
        # GIVEN
        await file_factory("user/a/f.txt")
        # WHEN
        await async_s3_storage.movedir(at=("user", "a/f.txt"), to=("user", "b/f.txt"))
        # THEN
        assert await async_s3_storage.exists("user", "a/f.txt")
        assert not await async_s3_storage.exists("user", "b/f.txt")

    async def test_when_source_does_not_exist(self, async_s3_storage: AsyncS3Storage):
        await async_s3_storage.movedir(at=("user", "a"), to=("user", "b"))

    async def test_when_destination_does_not_exist(
        self, file_factory, async_s3_storage: AsyncS3Storage
    ):
        # GIVEN
        await file_factory("user/a/x.txt")
        # WHEN
        await async_s3_storage.movedir(at=("user", "a"), to=("user", "b/a"))
        # THEN
        assert not await async_s3_storage.exists("user", "a/x.txt")
        assert await async_s3_storage.exists("user", "b/a/x.txt")

    @pytest.mark.skip("that operation should not be permitted")
    async def test_when_destination_is_not_a_dir(
        self, file_factory, async_s3_storage: AsyncS3Storage
    ):
        await file_factory("user/a/f.txt")
        await file_factory("user/y.txt")

        # with pytest.raises(ClientError) as excinfo:
        await async_s3_storage.movedir(at=("user", "a"), to=("user", "y.txt/a"))

        # based on MinIO version the error code will be one of
        # codes = ("AccessDenied", "XMinioParentIsObject")
        # assert excinfo.value.response["Error"]["Code"] in codes


class TestSave:
    async def test(self, s3_bucket: str, s3_resource, async_s3_storage: AsyncS3Storage):
        content = BytesIO(b"I'm Dummy file!")
        file = await async_s3_storage.save("user", "a/f.txt", content=content)

        obj = s3_resource.Object(s3_bucket, "user/a/f.txt")
        assert file.name == "f.txt"
        assert file.ns_path == "user"
        assert file.path == "a/f.txt"
        assert file.size == obj.content_length == 15
        assert file.is_dir() is False

    @pytest.mark.skip("that operation should not be allowed")
    async def test_when_path_is_not_a_dir(
        self, file_factory, async_s3_storage: AsyncS3Storage
    ):
        await file_factory("user/f.txt")

        # with pytest.raises(ClientError) as excinfo:
        await async_s3_storage.save("user", "f.txt/f.txt", content=BytesIO(b""))

        # based on MinIO version the error code will be one of
        # codes = ("AccessDenied", "XMinioParentIsObject")
        # assert excinfo.value.response["Error"]["Code"] in codes

    async def test_when_overrides_existing_file(
        self, file_factory, async_s3_storage: AsyncS3Storage
    ):
        await file_factory("user/f.txt")
        file = await async_s3_storage.save(
            "user", "f.txt", content=BytesIO(b"Hello, World!")
        )
        assert file.size == 13
