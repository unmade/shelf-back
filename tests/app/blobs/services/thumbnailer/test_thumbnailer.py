from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.blobs.domain import Blob
from app.toolkit import timezone
from app.toolkit.thumbnails import ThumbnailUnavailable

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from app.app.blobs.domain import IBlobContent
    from app.app.blobs.services import BlobThumbnailService

pytestmark = [pytest.mark.anyio]


def _make_blob(
    storage_key: str,
    chash: str | None = None,
    size: int = 10,
    media_type: str = "image/jpeg",
) -> Blob:
    return Blob(
        id=uuid.uuid7(),
        storage_key=storage_key,
        chash=chash if chash is not None else uuid.uuid4().hex,
        size=size,
        media_type=media_type,
        created_at=timezone.now()
    )


class TestIsSupported:
    @mock.patch("app.app.blobs.services.thumbnailer.thumbnailer.thumbnails")
    async def test(self, thumbnails_mock: MagicMock, thumbnailer: BlobThumbnailService):
        # GIVEN
        media_type = "plain/text"
        # WHEN
        result = thumbnailer.is_supported(media_type)
        # THEN
        assert result == thumbnails_mock.is_supported.return_value
        thumbnails_mock.is_supported.assert_called_once_with(media_type)


class TestGetStorageKey:
    async def test(self, thumbnailer: BlobThumbnailService):
        chash, size = "abcdef", 72
        path = thumbnailer.get_storage_key(chash, size)
        assert path == "thumbnails/ab/cd/ef/abcdef_72.webp"


class TestGenerate:
    async def test(
        self,
        thumbnailer: BlobThumbnailService,
        image_content: IBlobContent,
    ):
        # GIVEN
        sizes = [32, 64, 128]
        blob = _make_blob("admin/im.jpeg", chash="abcdef")
        storage = cast(mock.MagicMock, thumbnailer.storage)
        storage.exists.side_effect = [True, False, False]
        # WHEN
        await thumbnailer.generate(blob.chash, image_content.file, sizes=sizes)
        # THEN
        storage.exists.assert_has_awaits([
            mock.call(thumbnailer.get_storage_key(blob.chash, 32)),
            mock.call(thumbnailer.get_storage_key(blob.chash, 64)),
            mock.call(thumbnailer.get_storage_key(blob.chash, 128)),
        ])
        storage.makedirs.assert_has_awaits([
            mock.call("thumbnails/ab/cd/ef"),
            mock.call("thumbnails/ab/cd/ef"),
        ])
        assert storage.save.await_count == 2

    @mock.patch("app.app.blobs.services.thumbnailer.thumbnailer.thumbnails.thumbnail")
    async def test_when_file_not_thumbnailable(
        self,
        thumbnail_mock: MagicMock,
        thumbnailer: BlobThumbnailService,
        image_content: IBlobContent,
    ):
        # GIVEN
        sizes = [32, 64, 128]
        blob = _make_blob("admin/im.jpeg", chash="abcdef")
        storage = cast(mock.MagicMock, thumbnailer.storage)
        storage.exists.return_value = False
        thumbnail_mock.side_effect = ThumbnailUnavailable
        # WHEN
        await thumbnailer.generate(blob.chash, image_content.file, sizes=sizes)
        # THEN
        storage.exists.assert_awaited_once_with("thumbnails/ab/cd/ef/abcdef_32.webp")
        storage.makedirs.assert_not_called()
        storage.save.assert_not_called()

    async def test_when_file_size_exceed_limits(
        self,
        thumbnailer: BlobThumbnailService,
        image_content: IBlobContent,
    ):
        # GIVEN
        thumbnailer.max_file_size = image_content.size - 10
        sizes = [32, 64, 128]
        blob = _make_blob("admin/im.jpeg", size=image_content.size)
        storage = cast(mock.MagicMock, thumbnailer.storage)
        # WHEN
        await thumbnailer.generate(blob.chash, image_content.file, sizes=sizes)
        # THEN
        storage.exists.assert_not_called()
        storage.download.assert_not_called()
        storage.makedirs.assert_not_called()
        storage.save.assert_not_called()

    async def test_when_file_type_is_not_supported(
        self,
        thumbnailer: BlobThumbnailService,
        content: IBlobContent,
    ):
        # GIVEN
        sizes = [32, 64, 128]
        blob = _make_blob("admin/f.txt", media_type="plain/text")
        storage = cast(mock.MagicMock, thumbnailer.storage)
        # WHEN
        await thumbnailer.generate(blob.chash, content.file, sizes=sizes)
        # THEN
        storage.exists.assert_not_called()
        storage.download.assert_not_called()
        storage.makedirs.assert_not_called()
        storage.save.assert_not_called()

    async def test_when_chash_is_empty(
        self,
        thumbnailer: BlobThumbnailService,
        image_content: IBlobContent,
    ):
        # GIVEN
        sizes = [32, 64, 128]
        blob = _make_blob("admin/im.jpeg", chash="")
        storage = cast(mock.MagicMock, thumbnailer.storage)
        # WHEN
        await thumbnailer.generate(blob.chash, image_content.file, sizes=sizes)
        # THEN
        storage.exists.assert_not_called()
        storage.download.assert_not_called()
        storage.makedirs.assert_not_called()
        storage.save.assert_not_called()
