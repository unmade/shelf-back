from __future__ import annotations

import operator
from io import BytesIO
from typing import IO, TYPE_CHECKING
from zipfile import ZipFile

import pytest
from asgiref.sync import sync_to_async
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from app import errors
from app.infrastructure.storage.s3 import S3Storage

if TYPE_CHECKING:
    from app.typedefs import StrOrPath

pytestmark = [pytest.mark.asyncio, pytest.mark.storage_s3]


@pytest.fixture(scope="module")
def tmp_bucket() -> str:
    """A bucket name used in tests."""
    return "shelf-test"


@pytest.fixture(scope="module")
def s3_storage(tmp_bucket: str) -> S3Storage:
    """An instance of `S3Storage` with a `tmp_path` fixture as a location."""
    storage = S3Storage("http://localhost:9000")
    storage.bucket_name = tmp_bucket
    return storage


@pytest.fixture(scope="module")
def s3_resource(s3_storage: S3Storage):
    """An s3 resource client."""
    return s3_storage.s3


@pytest.fixture(autouse=True, scope="module")
def setup_bucket(tmp_bucket: str, s3_resource):  # pragma: no cover
    """Setups fixture to create a new bucket."""
    bucket = s3_resource.Bucket(tmp_bucket)

    try:
        bucket.create()
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "BucketAlreadyOwnedByYou":
            return
        raise


@pytest.fixture(autouse=True, scope="module")
def teardown_bucket(tmp_bucket: str, s3_resource):  # pragma: no cover
    """Teardown fixture to remove all files in the bucket, then remove the bucket."""
    try:
        yield
    finally:
        from botocore.exceptions import ClientError

        bucket = s3_resource.Bucket(tmp_bucket)

        try:
            bucket.load()
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "404":
                return
            raise

        bucket.objects.delete()
        bucket.delete()


@pytest.fixture(autouse=True)
def teatdown_files(tmp_bucket: str, s3_resource):
    """Teatdown fixture to clean up all files in the bucket after each test."""
    try:
        yield
    finally:
        bucket = s3_resource.Bucket(tmp_bucket)
        bucket.objects.delete()


@pytest.fixture
def file_factory(tmp_bucket: str, s3_resource):
    """
    A file factory for a S3Storage.

    Save file in a specified path with a given content and return full path.
    Any missing parents will be created.
    """
    @sync_to_async
    def create_file(
        path: StrOrPath,
        content: bytes | BytesIO = b"I'm Dummy File!",
    ) -> None:
        if isinstance(content, bytes):
            content = BytesIO(content)

        s3_resource.Bucket(tmp_bucket).upload_fileobj(content, path)

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


async def test_download(file_factory, s3_storage: S3Storage):
    await file_factory("user/f.txt")
    buffer = BytesIO()
    for chunk in s3_storage.download("user", "f.txt"):
        buffer.write(chunk)
    buffer.seek(0)
    assert buffer.read() == b"I'm Dummy File!"


async def test_download_but_it_is_a_dir(file_factory, s3_storage: S3Storage):
    await file_factory("user/a/f.txt")
    with pytest.raises(errors.FileNotFound):
        s3_storage.download("user", "a")


async def test_download_but_file_does_not_exists(s3_storage: S3Storage):
    with pytest.raises(errors.FileNotFound):
        s3_storage.download("user", "f.txt")


async def test_download_but_client_raises_error(s3_storage: S3Storage):
    stubber = Stubber(s3_storage.s3.meta.client)
    stubber.add_client_error("get_object")

    with stubber, pytest.raises(ClientError):
            s3_storage.download("user", "f.txt")


async def test_downloaddir(file_factory, s3_storage: S3Storage):
    await file_factory("user/a/x.txt", content=BytesIO(b"Hello"))
    await file_factory("user/a/y.txt", content=BytesIO(b"World"))
    await file_factory("user/a/c/f.txt", content=BytesIO(b"!"))
    await file_factory("user/b/z.txt")

    buffer = BytesIO()
    for chunk in s3_storage.downloaddir("user", "a"):
        buffer.write(chunk)
    buffer.seek(0)

    with ZipFile(buffer, "r") as archive:
        assert set(archive.namelist()) == {"x.txt", "y.txt", "c/f.txt"}
        assert archive.read("x.txt") == b"Hello"
        assert archive.read("y.txt") == b"World"
        assert archive.read("c/f.txt") == b"!"


async def test_downloaddir_on_empty_dir(file_factory, s3_storage: S3Storage):
    await file_factory("user/empty_dir/", content=b"")
    buffer = BytesIO()
    for chunk in s3_storage.downloaddir("user", "empty_dir"):
        buffer.write(chunk)
    buffer.seek(0)

    with ZipFile(buffer, "r") as archive:
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


async def test_get_modified(file_factory, s3_storage: S3Storage):
    await file_factory("user/f.txt")
    mtime = await s3_storage.get_modified_time("user", "f.txt")
    assert mtime > 0


async def test_get_modified_time_but_file_does_not_exist(s3_storage: S3Storage):
    with pytest.raises(errors.FileNotFound):
        await s3_storage.get_modified_time("user", "f.txt")


async def test_get_modified_time_but_client_raises_error(s3_storage: S3Storage):
    stubber = Stubber(s3_storage.s3.meta.client)
    stubber.add_client_error("head_object")

    with stubber, pytest.raises(ClientError):
            await s3_storage.get_modified_time("user", "f.txt")


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


async def test_move(file_factory, s3_storage: S3Storage):
    await file_factory("user/x.txt")
    await s3_storage.move("user", "x.txt", "y.txt")
    assert not await s3_storage.exists("user", "x.txt")
    assert await s3_storage.exists("user", "y.txt")


async def test_move_but_it_is_a_dir(file_factory, s3_storage: S3Storage):
    await file_factory("user/a/x.txt")

    with pytest.raises(errors.FileNotFound):
        await s3_storage.move("user", "a", "b")


async def test_move_but_source_does_not_exist(s3_storage: S3Storage):
    with pytest.raises(errors.FileNotFound):
        await s3_storage.move("user", "x.txt", "y.txt")


async def test_move_but_destination_does_not_exist(file_factory, s3_storage: S3Storage):
    await file_factory("user/x.txt")
    await s3_storage.move("user", "x.txt", "a/y.txt")
    assert not await s3_storage.exists("user", "x.txt")
    assert await s3_storage.exists("user", "a/y.txt")


async def test_move_but_destination_is_not_a_dir(file_factory, s3_storage: S3Storage):
    await file_factory("user/x.txt")
    await file_factory("user/y.txt")

    with pytest.raises(ClientError) as excinfo:
        await s3_storage.move("user", "x.txt", "y.txt/x.txt")

    # based on MinIO version the error code will be one of
    codes = ("AccessDenied", "XMinioParentIsObject")
    assert excinfo.value.response["Error"]["Code"] in codes


async def test_move_but_client_raises_error(s3_storage: S3Storage):
    stubber = Stubber(s3_storage.s3.meta.client)
    stubber.add_client_error("head_object")

    with stubber, pytest.raises(ClientError):
            await s3_storage.move("user", "x.txt", "y.txt/x.txt")


async def test_movedir(file_factory, s3_storage: S3Storage):
    await file_factory("user/a/f.txt")
    await file_factory("user/b/f.txt")

    await s3_storage.movedir("user", "a", "b/a")

    assert not await s3_storage.exists("user", "a")
    assert not await s3_storage.exists("user", "a/f.txt")
    assert await s3_storage.exists("user", "b/a")
    assert await s3_storage.exists("user", "b/a/f.txt")


async def test_movedir_on_empty_dir(file_factory, s3_storage: S3Storage):
    await file_factory("user/empty_dir/", content=b"")
    await s3_storage.movedir("user", "empty_dir", "a")
    assert not await s3_storage.exists("user", "empty_dir")
    assert await s3_storage.exists("user", "a")


async def test_movedir_but_it_is_a_file(file_factory, s3_storage: S3Storage):
    await file_factory("user/a/f.txt")

    await s3_storage.movedir("user", "a/f.txt", "b/f.txt")

    assert await s3_storage.exists("user", "a")
    assert await s3_storage.exists("user", "a/f.txt")
    assert not await s3_storage.exists("user", "b/f.txt")


async def test_movedir_but_source_does_not_exist(s3_storage: S3Storage):
    await s3_storage.movedir("user", "a", "b")


async def test_movedir_but_destination_does_not_exist(
    file_factory, s3_storage: S3Storage
):
    await file_factory("user/a/x.txt")
    await s3_storage.movedir("user", "a", "b/a")
    assert not await s3_storage.exists("user", "a/x.txt")
    assert await s3_storage.exists("user", "b/a/x.txt")


async def test_movedir_but_destination_is_not_a_dir(
    file_factory, s3_storage: S3Storage
):
    await file_factory("user/a/f.txt")
    await file_factory("user/y.txt")

    with pytest.raises(ClientError) as excinfo:
        await s3_storage.movedir("user", "a", "y.txt/a")

    # based on MinIO version the error code will be one of
    codes = ("AccessDenied", "XMinioParentIsObject")
    assert excinfo.value.response["Error"]["Code"] in codes


async def test_save(tmp_bucket: str, s3_resource, s3_storage: S3Storage):
    content = BytesIO(b"I'm Dummy file!")
    file = await s3_storage.save("user", "a/f.txt", content=content)

    obj = s3_resource.Object(tmp_bucket, "user/a/f.txt")
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


async def test_size(file_factory, s3_storage: S3Storage):
    await file_factory("user/f.txt")
    size = await s3_storage.size("user", "f.txt")
    assert size == 15


async def test_size_but_file_does_not_exist(s3_storage: S3Storage):
    with pytest.raises(errors.FileNotFound):
        await s3_storage.size("user", "f.txt")


async def test_size_but_client_raises_error(s3_storage: S3Storage):
    stubber = Stubber(s3_storage.s3.meta.client)
    stubber.add_client_error("head_object")

    with stubber, pytest.raises(ClientError):
            await s3_storage.size("user", "f.txt")


async def test_thumbnail(file_factory, image_content: IO[bytes], s3_storage: S3Storage):
    await file_factory("user/im.jpg", content=image_content)
    content = await s3_storage.thumbnail("user", "im.jpg", size=128)
    assert len(content) == 112


async def test_thumbnail_but_file_is_not_an_image(file_factory, s3_storage: S3Storage):
    await file_factory("user/im.jpg")

    with pytest.raises(errors.ThumbnailUnavailable) as excinfo:
        await s3_storage.thumbnail("user", "im.jpg", size=128)

    assert str(excinfo.value) == "Can't generate a thumbnail for a file: 'im.jpg'"


async def test_thumbnail_but_path_does_not_exist(s3_storage: S3Storage):
    with pytest.raises(errors.FileNotFound):
        await s3_storage.thumbnail("user", "im.jpg", size=128)


async def test_thumbnail_but_client_raises_error(s3_storage: S3Storage):
    stubber = Stubber(s3_storage.s3.meta.client)
    stubber.add_client_error("head_object")

    with stubber, pytest.raises(ClientError):
            await s3_storage.thumbnail("user", "im.jpg", size=128)
