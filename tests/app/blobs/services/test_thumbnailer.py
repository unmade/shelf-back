from __future__ import annotations

import uuid
from io import BytesIO
from typing import IO, TYPE_CHECKING, cast
from unittest import mock

import pytest

from app.app.blobs.domain import Blob
from app.toolkit import thumbnails, timezone
from app.toolkit.mediatypes import MediaType
from app.toolkit.thumbnails import ThumbnailUnavailable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from unittest.mock import MagicMock

    from app.app.blobs.domain import IBlobContent
    from app.app.blobs.services import BlobThumbnailService

pytestmark = [pytest.mark.anyio]


async def _aiter(content: IO[bytes]) -> AsyncIterator[bytes]:
    for chunk in content:
        yield chunk


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
    @mock.patch("app.app.blobs.services.thumbnailer.thumbnails")
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

    @mock.patch("app.app.blobs.services.thumbnailer.thumbnails.thumbnail")
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


class TestThumbnail:
    async def test_thumbnail_retrieved_from_storage(
        self,
        thumbnailer: BlobThumbnailService,
        image_content: IBlobContent,
    ):
        # GIVEN
        blob = _make_blob("admin/im.jpeg", chash="abcdef")
        thumbnail, _ = await thumbnails.thumbnail(image_content.file, size=32)
        storage = cast(mock.MagicMock, thumbnailer.storage)
        storage.exists.return_value = True
        storage.download.return_value = _aiter(BytesIO(thumbnail))
        # WHEN
        result = await thumbnailer.thumbnail(blob.id, blob.chash, 32)
        # THEN
        assert result == (thumbnail, MediaType.IMAGE_WEBP)
        storage.exists.assert_awaited_once_with(
            "thumbnails/ab/cd/ef/abcdef_32.webp"
        )
        storage.download.assert_called_once_with(
            "thumbnails/ab/cd/ef/abcdef_32.webp"
        )

    async def test_thumbnail_created_and_put_to_storage(
        self,
        thumbnailer: BlobThumbnailService,
        image_content: IBlobContent,
    ):
        # GIVEN
        blob = _make_blob("admin/im.jpeg", chash="abcdef")
        storage = cast(mock.MagicMock, thumbnailer.storage)
        storage.exists.return_value = False
        blob_service = cast(mock.MagicMock, thumbnailer.blob_service)
        blob_service.get_by_id.return_value = blob
        blob_service.download.return_value = _aiter(image_content.file)
        # WHEN
        thumbnail, mediatype = await thumbnailer.thumbnail(blob.id, blob.chash, 32)
        # THEN
        assert thumbnail
        assert mediatype == MediaType.IMAGE_WEBP
        blob_service.get_by_id.assert_awaited_once_with(blob.id)
        blob_service.download.assert_called_once_with(blob.storage_key)
        storage.makedirs.assert_awaited_once_with("thumbnails/ab/cd/ef")
        storage.save.assert_awaited_once()

    @mock.patch("app.app.blobs.services.thumbnailer.thumbnails.thumbnail")
    async def test_when_thumbnail_unavailable(
        self,
        thumbnail_mock: MagicMock,
        thumbnailer: BlobThumbnailService,
        image_content: IBlobContent,
    ):
        # GIVEN
        blob = _make_blob("admin/im.jpeg", chash="abcdef")
        storage = cast(mock.MagicMock, thumbnailer.storage)
        storage.exists.return_value = False
        blob_service = cast(mock.MagicMock, thumbnailer.blob_service)
        blob_service.get_by_id.return_value = blob
        blob_service.download.return_value = _aiter(image_content.file)
        thumbnail_mock.side_effect = ThumbnailUnavailable
        # WHEN / THEN
        with pytest.raises(Blob.ThumbnailUnavailable):
            await thumbnailer.thumbnail(blob.id, blob.chash, 32)

    async def test_when_blob_size_exceeds_limits(
        self,
        thumbnailer: BlobThumbnailService,
    ):
        # GIVEN
        blob_size = thumbnailer.max_file_size + 1
        blob = _make_blob("admin/im.jpeg", chash="abcdef", size=blob_size)
        storage = cast(mock.MagicMock, thumbnailer.storage)
        storage.exists.return_value = False
        blob_service = cast(mock.MagicMock, thumbnailer.blob_service)
        blob_service.get_by_id.return_value = blob
        # WHEN / THEN
        with pytest.raises(Blob.ThumbnailUnavailable):
            await thumbnailer.thumbnail(blob.id, blob.chash, 32)
        blob_service.download.assert_not_called()
        storage.makedirs.assert_not_called()
        storage.save.assert_not_called()

    async def test_when_chash_is_empty(self, thumbnailer: BlobThumbnailService):
        # GIVEN
        blob_id = uuid.uuid7()
        storage = cast(mock.MagicMock, thumbnailer.storage)
        # WHEN / THEN
        with pytest.raises(Blob.ThumbnailUnavailable):
            await thumbnailer.thumbnail(blob_id, "", 32)
        storage.exists.assert_not_called()
