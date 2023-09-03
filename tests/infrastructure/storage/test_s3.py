from __future__ import annotations

import operator
from io import BytesIO
from typing import TYPE_CHECKING
from zipfile import ZipFile

import pytest
from asgiref.sync import sync_to_async
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from app.app.files.domain import File
from app.infrastructure.storage.s3 import S3Storage

if TYPE_CHECKING:
    from app.app.files.domain import AnyPath

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


async def test_delete(file_factory, s3_storage: S3Storage):
    await file_factory("user/f.txt")
    assert await s3_storage.exists("user", "f.txt")
    await s3_storage.delete("user", "f.txt")
    assert not await s3_storage.exists("user", "f.txt")


async def test_delete_but_it_is_a_dir(file_factory, s3_storage: S3Storage):
    await file_factory("user/a/f.txt")
    await s3_storage.delete("user", "a")
    assert await s3_storage.exists("user", "a")
    assert await s3_storage.exists("user", "a/f.txt")


async def test_delete_but_file_does_not_exist(s3_storage: S3Storage):
    await s3_storage.delete("user", "f.txt")


async def test_deletedir(file_factory, s3_storage: S3Storage):
    await file_factory("user/a/f.txt")
    await s3_storage.deletedir("user", "a")
    assert not await s3_storage.exists("user", "a")
    assert not await s3_storage.exists("user", "a/f.txt")


async def test_deletedir_but_it_is_a_file(file_factory, s3_storage: S3Storage):
    await file_factory("user/f.txt")
    await s3_storage.deletedir("user", "f.txt")
    assert await s3_storage.exists("user", "f.txt")


async def test_deletedir_but_dir_does_not_exist(s3_storage: S3Storage):
    await s3_storage.deletedir("user", "a")


async def test_emptydir(file_factory, s3_storage: S3Storage):
    await file_factory("user/a/f.txt")
    await file_factory("user/a/b/f.txt")
    await s3_storage.emptydir("user", "a")
    assert not await s3_storage.exists("user", "a")
    assert not await s3_storage.exists("user", "a/f.txt")
    assert not await s3_storage.exists("user", "a/b")
    assert not await s3_storage.exists("user", "a/b/f.txt")


async def test_emptydir_but_it_is_a_file(file_factory, s3_storage: S3Storage):
    await file_factory("user/f.txt")
    await s3_storage.emptydir("user", "f.txt")
    assert await s3_storage.exists("user", "f.txt")


async def test_emptydir_but_dir_does_not_exist(s3_storage: S3Storage):
    await s3_storage.emptydir("user", "a")


class TestDownload:
    async def test(self, file_factory, s3_storage: S3Storage):
        # GIVEN
        await file_factory("user/f.txt")
        # WHEN
        content_reader = await s3_storage.download("user", "f.txt")
        # THEN
        assert content_reader.zipped is False
        content = await content_reader.stream()
        assert content.read() == b"I'm Dummy File!"

    async def test_when_it_is_a_dir(self, file_factory, s3_storage: S3Storage):
        await file_factory("user/a/f.txt")
        with pytest.raises(File.NotFound):
            await s3_storage.download("user", "a")

    async def test_when_file_does_not_exist(self, s3_storage: S3Storage):
        with pytest.raises(File.NotFound):
            await s3_storage.download("user", "f.txt")

    async def test_when_client_raises_error(self, s3_storage: S3Storage):
        stubber = Stubber(s3_storage.s3.meta.client)
        stubber.add_client_error("get_object")
        with stubber, pytest.raises(ClientError):
            await s3_storage.download("user", "f.txt")


class TestDownloadDir:
    async def test(self, file_factory, s3_storage: S3Storage):
        # GIVEN
        await file_factory("user/a/x.txt", content=BytesIO(b"Hello"))
        await file_factory("user/a/y.txt", content=BytesIO(b"World"))
        await file_factory("user/a/c/f.txt", content=BytesIO(b"!"))
        await file_factory("user/b/z.txt")

        # WHEN
        content_reader = await s3_storage.downloaddir("user", "a")

        # THEN
        assert content_reader.zipped is True
        content = await content_reader.stream()

        with ZipFile(content, "r") as archive:
            assert set(archive.namelist()) == {"x.txt", "y.txt", "c/f.txt"}
            assert archive.read("x.txt") == b"Hello"
            assert archive.read("y.txt") == b"World"
            assert archive.read("c/f.txt") == b"!"

    async def test_on_empty_dir(self, file_factory, s3_storage: S3Storage):
        # GIVEN
        await file_factory("user/empty_dir/", content=b"")
        # WHEN
        content_reader = await s3_storage.downloaddir("user", "empty_dir")
        # THEN
        content = await content_reader.stream()
        with ZipFile(content, "r") as archive:
            assert archive.namelist() == []

    async def test_when_dir_does_not_exist(self, s3_storage: S3Storage):
        content_reader = await s3_storage.downloaddir("user", "empty_dir")
        content = await content_reader.stream()
        with ZipFile(content, "r") as archive:
            assert archive.namelist() == []


async def test_exists(file_factory, s3_storage: S3Storage):
    assert not await s3_storage.exists("user", "a")
    assert not await s3_storage.exists("user", "a/f.txt")
    await file_factory("user/a/f.txt")
    assert await s3_storage.exists("user", "a")
    assert await s3_storage.exists("user", "a/f.txt")


async def test_exists_but_client_raises_error(s3_storage: S3Storage):
    stubber = Stubber(s3_storage.s3.meta.client)
    stubber.add_client_error("head_object")

    with stubber, pytest.raises(ClientError):
            await s3_storage.exists("user", "f.txt")


async def test_iterdir(file_factory, s3_storage: S3Storage):
    await file_factory("user/a/x.txt")
    await file_factory("user/a/y.txt")
    await file_factory("user/a/c/f.txt")
    await file_factory("user/b/z.txt")

    c, x, y = sorted(
        await s3_storage.iterdir("user", "a"),
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


async def test_iterdir_on_empty_dir(file_factory, s3_storage: S3Storage):
    await file_factory("user/empty_dir/", content=b"")
    files = list(await s3_storage.iterdir("user", "empty_dir"))
    assert files == []


async def test_iterdir_but_path_does_not_exist(s3_storage: S3Storage):
    assert len(list(await s3_storage.iterdir("user", "a"))) == 0


async def test_iterdir_but_it_is_a_file(file_factory, s3_storage: S3Storage):
    await file_factory("user/f.txt")
    assert len(list(await s3_storage.iterdir("user", "f.txt"))) == 0


async def test_makedirs_is_a_noop(s3_storage: S3Storage):
    await s3_storage.makedirs("user", "f.txt")


class TestMove:
    async def test(self, file_factory, s3_storage: S3Storage):
        # GIVEN
        await file_factory("user/x.txt")
        # WHEN
        await s3_storage.move(at=("user", "x.txt"), to=("user", "y.txt"))
        # THEN
        assert not await s3_storage.exists("user", "x.txt")
        assert await s3_storage.exists("user", "y.txt")

    async def test_when_it_is_a_dir(self, file_factory, s3_storage: S3Storage):
        await file_factory("user/a/x.txt")

        with pytest.raises(File.NotFound):
            await s3_storage.move(at=("user", "a"), to=("user", "b"))

    async def test_when_source_does_not_exist(self, s3_storage: S3Storage):
        with pytest.raises(File.NotFound):
            await s3_storage.move(at=("user", "x.txt"), to=("user", "y.txt"))

    async def test_when_destination_does_not_exist(
        self, file_factory, s3_storage: S3Storage
    ):
        # GIVEN
        await file_factory("user/x.txt")
        # WHEN
        await s3_storage.move(at=("user", "x.txt"), to=("user", "a/y.txt"))
        # THEN
        assert not await s3_storage.exists("user", "x.txt")
        assert await s3_storage.exists("user", "a/y.txt")

    async def test_when_destination_is_not_a_dir(
        self, file_factory, s3_storage: S3Storage
    ):
        await file_factory("user/x.txt")
        await file_factory("user/y.txt")

        with pytest.raises(ClientError) as excinfo:
            await s3_storage.move(at=("user", "x.txt"), to=("user", "y.txt/x.txt"))

        # based on MinIO version the error code will be one of
        codes = ("AccessDenied", "XMinioParentIsObject")
        assert excinfo.value.response["Error"]["Code"] in codes

    async def test_when_client_raises_error(self, s3_storage: S3Storage):
        stubber = Stubber(s3_storage.s3.meta.client)
        stubber.add_client_error("head_object")

        with stubber, pytest.raises(ClientError):
                await s3_storage.move(at=("user", "x.txt"), to=("user", "y.txt/x.txt"))


class TestMoveDir:
    async def test(self, file_factory, s3_storage: S3Storage):
        # GIVEN
        await file_factory("user/a/f.txt")
        await file_factory("user/b/f.txt")
        # WHEN
        await s3_storage.movedir(at=("user", "a"), to=("user", "b/a"))
        # THEN
        assert not await s3_storage.exists("user", "a")
        assert not await s3_storage.exists("user", "a/f.txt")
        assert await s3_storage.exists("user", "b/a")
        assert await s3_storage.exists("user", "b/a/f.txt")

    async def test_on_empty_dir(self, file_factory, s3_storage: S3Storage):
        # GIVEN
        await file_factory("user/empty_dir/", content=b"")
        # WHEN
        await s3_storage.movedir(at=("user", "empty_dir"), to=("user", "a"))
        # THEN
        assert not await s3_storage.exists("user", "empty_dir")
        assert await s3_storage.exists("user", "a")

    async def test_when_it_is_a_file(self, file_factory, s3_storage: S3Storage):
        # GIVEN
        await file_factory("user/a/f.txt")
        # WHEN
        await s3_storage.movedir(at=("user", "a/f.txt"), to=("user", "b/f.txt"))
        # THEN
        assert await s3_storage.exists("user", "a")
        assert await s3_storage.exists("user", "a/f.txt")
        assert not await s3_storage.exists("user", "b/f.txt")

    async def test_when_source_does_not_exist(self, s3_storage: S3Storage):
        await s3_storage.movedir(at=("user", "a"), to=("user", "b"))

    async def test_when_destination_does_not_exist(
        self, file_factory, s3_storage: S3Storage
    ):
        # GIVEN
        await file_factory("user/a/x.txt")
        # WHEN
        await s3_storage.movedir(at=("user", "a"), to=("user", "b/a"))
        # THEN
        assert not await s3_storage.exists("user", "a/x.txt")
        assert await s3_storage.exists("user", "b/a/x.txt")

    async def test_when_destination_is_not_a_dir(
        self, file_factory, s3_storage: S3Storage
    ):
        await file_factory("user/a/f.txt")
        await file_factory("user/y.txt")

        with pytest.raises(ClientError) as excinfo:
            await s3_storage.movedir(at=("user", "a"), to=("user", "y.txt/a"))

        # based on MinIO version the error code will be one of
        codes = ("AccessDenied", "XMinioParentIsObject")
        assert excinfo.value.response["Error"]["Code"] in codes


async def test_save(s3_bucket: str, s3_resource, s3_storage: S3Storage):
    content = BytesIO(b"I'm Dummy file!")
    file = await s3_storage.save("user", "a/f.txt", content=content)

    obj = s3_resource.Object(s3_bucket, "user/a/f.txt")
    assert file.name == "f.txt"
    assert file.ns_path == "user"
    assert file.path == "a/f.txt"
    assert file.size == obj.content_length == 15
    assert file.is_dir() is False


async def test_save_but_path_is_not_a_dir(file_factory, s3_storage: S3Storage):
    await file_factory("user/f.txt")

    with pytest.raises(ClientError) as excinfo:
        await s3_storage.save("user", "f.txt/f.txt", content=BytesIO(b""))

    # based on MinIO version the error code will be one of
    codes = ("AccessDenied", "XMinioParentIsObject")
    assert excinfo.value.response["Error"]["Code"] in codes


async def test_save_overrides_existing_file(file_factory, s3_storage: S3Storage):
    await file_factory("user/f.txt")
    file = await s3_storage.save("user", "f.txt", content=BytesIO(b"Hello, World!"))
    assert file.size == 13
