from __future__ import annotations

import uuid
from io import BytesIO
from typing import IO, TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.files.domain import File, Path
from app.app.files.services.thumbnailer import thumbnails
from app.app.files.services.thumbnailer.thumbnailer import _PREFIX
from app.config import config

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from unittest.mock import MagicMock

    from app.app.files.domain import AnyPath, IFileContent
    from app.app.files.services import ThumbnailService

pytestmark = [pytest.mark.anyio]


async def _aiter(content: IO[bytes]) -> AsyncIterator[bytes]:
    for chunk in content:
        yield chunk


def _make_file(
    ns_path: str,
    path: AnyPath,
    chash: str | None = None,
    size: int = 10,
    mediatype: str = "image/jpeg",
) -> File:
    path = Path(path)
    return File(
        id=uuid.uuid4(),
        ns_path=ns_path,
        name=path.name,
        path=path,
        chash=chash if chash is not None else uuid.uuid4().hex,
        size=size,
        mediatype=mediatype,
    )


@pytest.fixture
async def image_thumbnail(image_content: IFileContent) -> bytes:
    """Create a thumbnail from `image_content` fixture with size of 32."""
    thumbnail = await thumbnails.thumbnail(image_content.file, size=32)
    await image_content.seek(0)
    return thumbnail


class TestGetStoragePath:
    async def test(self, thumbnailer: ThumbnailService):
        chash, size = "abcdef", 72
        path = thumbnailer.get_storage_path(chash, size)
        assert path == "thumbs/ab/cd/ef/abcdef_72.webp"


class TestGenerateThumbnails:
    async def test(
        self,
        thumbnailer: ThumbnailService,
        image_content: IFileContent,
    ):
        # GIVEN
        sizes = [32, 64, 128]
        file = _make_file("admin", "im.jpeg", chash="abcdef")
        filecore = cast(mock.MagicMock, thumbnailer.filecore)
        filecore.get_by_id.return_value = file
        filecore.download.return_value = file, _aiter(image_content.file)
        storage = cast(mock.MagicMock, thumbnailer.storage)
        storage.exists.side_effect = [True, False, False]
        # WHEN
        await thumbnailer.generate_thumbnails(file.id, sizes=sizes)
        # THEN
        filecore.get_by_id.assert_awaited_once_with(file.id)
        storage.exists.assert_has_awaits([
            mock.call(_PREFIX, thumbnailer._make_path(file.chash, 32)),
            mock.call(_PREFIX, thumbnailer._make_path(file.chash, 64)),
            mock.call(_PREFIX, thumbnailer._make_path(file.chash, 128)),
        ])
        filecore.download.assert_awaited_once_with(file.id)
        storage.makedirs.assert_has_awaits([
            mock.call(_PREFIX, "ab/cd/ef"),
            mock.call(_PREFIX, "ab/cd/ef"),
        ])
        assert storage.save.await_count == 2

    @mock.patch("app.app.files.services.thumbnailer.thumbnails.thumbnail")
    async def test_when_file_not_thumbnailable(
        self,
        thumbnail_mock: MagicMock,
        thumbnailer: ThumbnailService,
        image_content: IFileContent,
    ):
        # GIVEN
        sizes = [32, 64, 128]
        file = _make_file("admin", "im.jpeg", chash="abcdef")
        filecore = cast(mock.MagicMock, thumbnailer.filecore)
        filecore.get_by_id.return_value = file
        filecore.download.return_value = file, _aiter(image_content.file)
        storage = cast(mock.MagicMock, thumbnailer.storage)
        storage.exists.return_value = False
        thumbnail_mock.side_effect = File.ThumbnailUnavailable
        # WHEN
        await thumbnailer.generate_thumbnails(file.id, sizes=sizes)
        # THEN
        filecore.get_by_id.assert_awaited_once_with(file.id)
        storage.exists.assert_awaited_once_with(_PREFIX, "ab/cd/ef/abcdef_32.webp")
        filecore.download.assert_awaited_once_with(file.id)
        storage.makedirs.assert_not_called()
        storage.save.assert_not_called()

    async def test_when_file_size_exceed_limits(
        self,
        thumbnailer: ThumbnailService,
    ):
        # GIVEN
        file_size = config.features.max_file_size_to_thumbnail + 1
        sizes = [32, 64, 128]
        file = _make_file("admin", "im.jpeg", chash="abcdef", size=file_size)
        filecore = cast(mock.AsyncMock, thumbnailer.filecore)
        filecore.get_by_id.return_value = file
        storage = cast(mock.MagicMock, thumbnailer.storage)
        # WHEN
        await thumbnailer.generate_thumbnails(file.id, sizes=sizes)
        # THEN
        filecore.get_by_id.assert_awaited_once_with(file.id)
        storage.exists.assert_not_called()
        storage.download.assert_not_called()
        filecore.download.assert_not_called()
        storage.makedirs.assert_not_called()
        storage.save.assert_not_called()

    async def test_when_file_type_is_not_supported(
        self,
        thumbnailer: ThumbnailService,
    ):
        # GIVEN
        sizes = [32, 64, 128]
        file = _make_file("admin", "f.txt", mediatype="plain/text")
        filecore = cast(mock.AsyncMock, thumbnailer.filecore)
        filecore.get_by_id.return_value = file
        storage = cast(mock.MagicMock, thumbnailer.storage)
        # WHEN
        await thumbnailer.generate_thumbnails(file.id, sizes=sizes)
        # THEN
        filecore.get_by_id.assert_awaited_once_with(file.id)
        storage.exists.assert_not_called()
        storage.download.assert_not_called()
        filecore.download.assert_not_called()
        storage.makedirs.assert_not_called()
        storage.save.assert_not_called()

    async def test_when_chash_is_empty(self, thumbnailer: ThumbnailService):
        # GIVEN
        sizes = [32, 64, 128]
        file = _make_file("admin", "im.jpeg", chash="")
        filecore = cast(mock.AsyncMock, thumbnailer.filecore)
        filecore.get_by_id.return_value = file
        storage = cast(mock.MagicMock, thumbnailer.storage)
        # WHEN
        await thumbnailer.generate_thumbnails(file.id, sizes=sizes)
        # THEN
        filecore.get_by_id.assert_awaited_once_with(file.id)
        storage.exists.assert_not_called()
        storage.download.assert_not_called()
        filecore.download.assert_not_called()
        storage.makedirs.assert_not_called()
        storage.save.assert_not_called()


class TestThumbnail:
    async def test_thumbnail_retrieved_from_storage(
        self,
        thumbnailer: ThumbnailService,
        image_thumbnail: bytes,
    ):
        # GIVEN
        file_id, content_hash, size = uuid.uuid4(), "abcdef", 32
        t_path = "ab/cd/ef/abcdef_32.webp"
        filecore = cast(mock.MagicMock, thumbnailer.filecore)
        storage = cast(mock.MagicMock, thumbnailer.storage)
        storage.download.return_value = _aiter(BytesIO(image_thumbnail))
        # WHEN
        result = await thumbnailer.thumbnail(file_id, content_hash, size)
        # THEN
        assert result == image_thumbnail
        storage.exists.assert_awaited_once_with(_PREFIX, t_path)
        storage.download.assert_called_once_with(_PREFIX, t_path)
        filecore.download.assert_not_called()

    async def test_thumbnail_created_and_put_to_storage(
        self,
        thumbnailer: ThumbnailService,
        image_content: IFileContent,
    ):
        # GIVEN
        file, size = _make_file("admin", "im.jpeg", chash="abcdef"), 32
        t_path = "ab/cd/ef/abcdef_32.webp"
        filecore = cast(mock.AsyncMock, thumbnailer.filecore)
        filecore.download.return_value = file, _aiter(image_content.file)
        storage = cast(mock.MagicMock, thumbnailer.storage)
        storage.exists.return_value = False
        # WHEN
        thumbnail = await thumbnailer.thumbnail(file.id, file.chash, size)
        # THEN
        assert thumbnail == await thumbnails.thumbnail(image_content.file, size=size)
        storage.exists.assert_awaited_once_with(_PREFIX, t_path)
        storage.download.assert_not_called()
        filecore.download.assert_awaited_once_with(file.id)
        storage.makedirs.assert_awaited_once_with(_PREFIX, "ab/cd/ef")
        storage.save.assert_awaited_once()

    async def test_when_file_size_exceed_limits(
        self,
        thumbnailer: ThumbnailService,
    ):
        # GIVEN
        file_size = config.features.max_file_size_to_thumbnail + 1
        file, size = _make_file("admin", "im.jpeg", size=file_size), 32
        filecore = cast(mock.AsyncMock, thumbnailer.filecore)
        filecore.download.return_value = file, mock.ANY
        storage = cast(mock.MagicMock, thumbnailer.storage)
        storage.exists.return_value = False
        # WHEN
        with pytest.raises(File.ThumbnailUnavailable):
            await thumbnailer.thumbnail(file.id, file.chash, size)
        # THEN
        storage.exists.assert_awaited_once()
        storage.download.assert_not_called()
        filecore.download.assert_awaited_once_with(file.id)
        storage.makedirs.assert_not_called()
        storage.save.assert_not_called()

    async def test_when_chash_is_empty(self, thumbnailer: ThumbnailService):
        # GIVEN
        file, size = _make_file("admin", "im.jpeg", chash=""), 32
        filecore = cast(mock.AsyncMock, thumbnailer.filecore)
        storage = cast(mock.MagicMock, thumbnailer.storage)
        # WHEN
        with pytest.raises(File.ThumbnailUnavailable):
            await thumbnailer.thumbnail(file.id, file.chash, size)
        # THEN
        storage.exists.assert_not_called()
        storage.download.assert_not_called()
        filecore.download.assert_not_called()
        storage.makedirs.assert_not_called()
        storage.save.assert_not_called()
